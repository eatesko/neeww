import uuid
import numpy as np
import pandas as pd
import pytz as tz
import csv
from os.path import join

from celery.result import AsyncResult
from datetime import datetime, date, time, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse
from django.views import generic
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import F
from django.contrib.auth.models import Group
from django.contrib.sites.shortcuts import get_current_site

from django.conf import settings
from django.contrib import messages

from .models import (Survey, SurveyQuestion, SurveyChoice, Response,
				 ResponseQuestion, ResponseChoice, SurveyProperties)
from users.models import MyUser, SurveyOfferRecords, Reward, ResponseTimer, SurveyNotification
from users.views import send_user_activation_link
from tesis_celery.tasks import share_survey

from surveys.forms import SurveyForm
from users.forms import RespondentRegisterForm

# Create your views here.
class SurveyIndex(PermissionRequiredMixin, generic.ListView):
	permission_required = 'surveys.add_survey'

	template_name = 'surveys/survey_list.html'

	def get_queryset(self):
		return Survey.objects.all()

class ResponseIndex(LoginRequiredMixin, generic.ListView):
	template_name = 'surveys/response_list.html'

	def get_queryset(self):
		return Response.objects.all()

@csrf_protect
@login_required
def SurveyDetails(request, pk):
	try:
		survey = get_object_or_404(Survey,
			pk=pk,
		)
	except:
		return HttpResponse('Invalid link address')

	survey_timer = timezone.now() + timedelta(
					minutes=survey.surveyproperties.survey_timer)

	if True: #New Test (not recent_survey == str(link_address):)
		# If the current survey is not the previous survey, set new 'survey timer'.
		request.session['survey_timer'] = str(survey_timer)

	# Get session 'survey timer' string and convert to datetime object type.
	timer = pd.to_datetime(request.session.get(
		'survey_timer', str(survey_timer))).to_pydatetime()

	"""session_timer = pd.to_datetime(request.session.get(
		'survey_timer', str(survey_timer))).to_pydatetime()"""

	formatted_timer = timer.strftime('%Y/%m/%d %H:%M:%S')

	template_name = 'surveys/survey_view.html'
	context = {
		'survey': survey,
		'server_timer': formatted_timer,
	}

	return render(request, template_name, context)

def ASurveyDetails(request, pk):
	try:
		survey = get_object_or_404(Survey,
			pk=pk,
		)
	except:
		return HttpResponse('Invalid link address')

	if request.user.is_authenticated:
		return redirect('surveys:survey', survey.link_address)

	template_name = 'surveys/survey_view.html'
	form = RespondentRegisterForm

	survey_timer = timezone.now() + timedelta(
				minutes=survey.surveyproperties.survey_timer)

	""" Session Based survey-timer for keeping track of survey-timer
	session_timer = pd.to_datetime(request.session.get(
		'survey_timer', str(survey_timer))).to_pydatetime()"""

	if True: #New Test (not recent_survey == str(link_address):)
		# If the current survey is not the previous survey, set new 'survey timer'.
		request.session['survey_timer'] = str(survey_timer)

	# Get session 'survey timer' string and convert to datetime object type.
	timer = pd.to_datetime(request.session.get(
		'survey_timer', str(survey_timer))).to_pydatetime()

	formatted_timer = timer.strftime('%Y/%m/%d %H:%M:%S')

	context = {
		'survey': survey,
		'form': form,
		'server_timer': formatted_timer,
	}

	return render(request, template_name, context)


class Progress(generic.DetailView):
	model = Survey
	context_object_name = 'survey'
	template_name = 'surveys/progress.html'

	def get_queryset(self):
		return Survey.objects.all()

class ResponseDetails(LoginRequiredMixin, generic.DetailView):
	model = Response
	context_object_name = 'response'
	template_name = 'surveys/response_view.html'

	def get_queryset(self):
		return Response.objects.all()


"""		Allows a user to create a new survey 	"""
"""@csrf_protect
@login_required
def create_survey(request):
	user = get_object_or_404(MyUser, email=request.user.email)
	context = {'user': user,}

	question_choice_list = []
	question_number = 1
	choice_number = 1

	if request.method == 'POST':
		post_data = dict(request.POST)
		post_data.pop('csrfmiddlewaretoken')

		title = request.POST['title']
		description = request.POST['description']

		post_data.pop('title')
		post_data.pop('description')

		for key_name in post_data:
			question_choice_list.append(key_name)
		question_choice_list.sort()

		for text_field_name in question_choice_list:
			if text_field_name[-1] == '0': # If the html field name represents that of a question's input
				choice_number = 1
				if question_number == 1: # If the loop has just began with the first question
					url = Survey.objects.create(
							user=user,
						  	title=title,
							print(question_choice_list),
						  	description=description,
						  	category='HEALTH & MEDICINE',
						  	date_created=timezone.now(),
						  	survey_option='F',
						  	sample_size=10,
						)
					url_question = url.surveyquestion_set.create(
									html_name=text_field_name,
									question_text=request.POST[text_field_name])
					#// Create survey properties
					#survey.survey_properties
					url_question.save()

					question_number += 1
				else: # If the loop is not on the first question
					# Associate the current question to the survey of the first question
					url = Survey.objects.get(pk=url.link_address)
					url_question = url.surveyquestion_set.create(
									html_name=text_field_name,
									question_text=request.POST[text_field_name])
					url_question.save()
					question_number += 1
			elif type(text_field_name[-1]) == int: # If the html field name represents that of a choice's input
				if choice_number == 1: # If the current choice is the first choice
					# Create a choice and associate it to the current question
					choice_question = SurveyQuestion.objects.get(pk=url_question.id)
					question_choice = choice_question.surveychoice_set.create(
										html_name=text_field_name,
										choice_text=request.POST[text_field_name])
					question_choice.save()
					choice_number += 1
				else: # If the current choice is not the first choice
					if text_field_name[-4] == str((question_number - 1)): # Verify whether the choice is part of the current question.
						# Create and associate the current choice to the question of the first choice
						choice_question = SurveyQuestion.objects.get(pk=choice_question.id)
						question_choice = choice_question.surveychoice_set.create(
											html_name=text_field_name,
											choice_text=request.POST[text_field_name])
						question_choice.save()
			else:
				pass

		share_survey.delay(url.link_address) # Notify users about the newly created survey

		return redirect('surveys:survey_update', url.link_address)

	return render(request, 'surveys/editjs.html', context)"""

@csrf_protect
@login_required
def create_survey(request):
	user = get_object_or_404(MyUser, email=request.user.email)
	template_name = "surveys/create_survey.html"

	f_message = "{} {}".format(
			"Create Surveys and get reliable responses at no cost. Survey",
			"data will be public to other Researcher's at a cost."
		)

	p_message = "{} {} {}".format(
			"Your Survey data will be private to you alone.",
			"Also maximize reliable response rate, since Respondents will",
			"be rewarded for responding to your Survey."
		)

	form = SurveyForm
	context = {'form': form, 'p_message': p_message, 'f_message': f_message}

	if request.method == "POST":
		survey = Survey.objects.create(
			user=user,
			field=request.POST["field"],
			survey_option=request.POST["option"],
			sample_size=request.POST["size"],
			date_created=timezone.now()
		)
		survey.save()
		survey.survey_properties

		success_message = "Free Survey was created successfully."
		messages.success(request, success_message)

		return redirect('surveys:survey_update', survey.link_address)
	return render(request, template_name, context)

"""		Takes care of modifying a survey a user created(A user must be the creator of the survey)	"""
@csrf_protect
@login_required
def update_survey(request, link_address):
	user = get_object_or_404(MyUser, email=request.user.email)
	survey = get_object_or_404(Survey, pk=link_address)

	context = {'survey': survey, 'user': user}

	if request.method == 'POST':
		question_choice_list = []

		total_questions = survey.surveyquestion_set.count() + 1

		post_data = dict(request.POST)
		post_data.pop('csrfmiddlewaretoken')

		title = request.POST['title']
		description = request.POST['description']

		post_data.pop('title')
		post_data.pop('description')
		post_data.pop('x')
		post_data.pop('y')

		for key_name in post_data:
			question_choice_list.append(key_name)
		question_choice_list.sort()

		survey.title = title
		survey.description = description

		"""index = 0
		question_number = 1
		choice_number = 1

		survey_question_choice_list = []

		for question_object in survey.surveyquestion_set.all():
			if question_choice_list:
				if (question_choice_list[index][-1] == '0'
				and question_object.html_name[2] == str(question_number)):
					question_object.question_text = request.POST[
						question_choice_list[index]]
					choice_number = 1
					question_number += 1
					question_choice_list.pop(index)
				else:
					for choice_object in question_object.surveychoice_set.all():
						if (
						question_choice_list[index][-1] == str(choice_number)
						and choice_object.html_name == str(choice_number)):
							choice_object.choice_text = request.POST[
								question_choice_list[index]]
							question_choice_list.pop(index)
							choice_number += 1
		print(question_choice_list)

		#mappings = zip(survey_question_choice_list, question_choice_list)
		print('next')



		for db_object in survey_question_choice_list:
			#print(db_object.html_name[5])
			if (db_object.html_name[5] == '0'
				and db_object.html_name[2] == str(question_number)):
				if (question_choice_list[index][2] == str(question_number)
						and question_choice_list[index][-1] == '0'):
					print(question_choice_list[index])
					db_object.question_text = request.POST[
						question_choice_list[index]]
					print('beforeq')
					print(survey_question_choice_list)
					survey_question_choice_list.remove(db_object)
					print('afterq')
					print(survey_question_choice_list)
					index += 1
					question_number += 1
					choice_number = 1
			elif (db_object.html_name[5] == str(choice_number)
				and db_object.html_name[2] == str(question_number)):
				if question_choice_list[index][-1] == str(choice_number):
					print(question_choice_list[index])
					db_object.choice_text = request.POST[
						question_choice_list[index]]
					print('beforec')
					print(survey_question_choice_list)
					survey_question_choice_list.remove(db_object)
					print('afterc')
					print(survey_question_choice_list)
					index += 1
					choice_number += 1
		print(survey_question_choice_list)"""
		survey.surveyquestion_set.all().delete()

		for text_field_name in question_choice_list:
			if text_field_name[-1] == '0':
				try:
					survey_question = survey.surveyquestion_set.get(
								question_number=text_field_name[2])
				except (KeyError, SurveyQuestion.DoesNotExist):
					survey_question = survey.surveyquestion_set.create(
									html_name=text_field_name,
									question_text=request.POST[text_field_name],
									question_number=text_field_name[2])
				else:
					survey_question.question_text = request.POST[text_field_name]
					survey_question.html_name = text_field_name
				survey_question.save()

			else:
				try:
					question_choice = survey_question.surveychoice_set.get(
								choice_number=text_field_name[5])
				except (KeyError, SurveyChoice.DoesNotExist):
					question_choice = survey_question.surveychoice_set.create(
										html_name=text_field_name,
										choice_text=request.POST[text_field_name],
										choice_number=text_field_name[5])
				else:
					question_choice.choice_text = request.POST[text_field_name]
					question_choice.html_name = text_field_name
				question_choice.save()

		survey.save()

		success_message = "Survey was updated successfully."
		messages.success(request, success_message)

		return redirect('surveys:survey_update', survey.link_address)

	return render(request, 'surveys/survey_edit_page.html', context)

@csrf_protect
@login_required
def update_survey_properties(request, link_address):
	#link_address = request.POST.get('link')
	user = get_object_or_404(MyUser, email=request.user.email)
	try:
			survey = get_object_or_404(Survey,
					pk=link_address,
				)
	except:
		return HttpResponse('Invalid link address')

	if request.method == 'POST':

		s_properties = survey.survey_properties
		non_reported = []

		if not s_properties.published:
			for r_survey in user.survey_set.all():
				if r_survey.completed and not r_survey.report:
					non_reported.append(r_survey.title)

			if non_reported:
				error_message = 'The following Survey(s) with title(s) \
					"{}" must be given a report before you can \
					publish another Survey. \
					Go to "Survey Properties" to fix this.'.format(
						", ".join(non_reported)
					)
				messages.error(request, error_message)

				return redirect('surveys:surveys')

			if survey.surveyquestion_set.all():
				s_properties.r_code = request.POST['r_code']
				s_properties.survey_timer = request.POST['survey_timer']
				s_properties.published = True
				s_properties.published_date = timezone.now()
			else:
				error_message = "Create some questions for \
				 this survey before you can publish it."
				messages.error(request, error_message)

				return redirect('surveys:survey_update', survey.link_address)
		else:
			s_properties.r_code = request.POST['r_code']
			s_properties.survey_timer = request.POST['survey_timer']
		s_properties.save()

		success_message = "Survey properties was updated successfully."
		messages.success(request, success_message)

		return redirect('surveys:survey_properties', link_address)

	total_price = settings.UNIT_PRICE * survey.sample_size
	current_site = get_current_site(request)
	context = {
		'survey': survey,
		'domain': current_site.domain,
		'total_price': total_price
	}

	return render(request, 'surveys/survey_properties.html', context)

@csrf_protect
@login_required
def survey_report(request, link_address):
	if request.method == "POST":
		try:
			survey = get_object_or_404(Survey,
					pk=request.POST.get('link_address', ''),
				)
		except:
			return HttpResponse('Invalid link address')

		if len(str(request.POST['report'])) >= 20:
			if not survey.report:
				survey.report = request.POST['report'] + "\n\n{}: {}".format(
					"Report Date/Time",
					timezone.now()
				)
				survey.save()

				success_message = "Your 'Survey Report' was \
					submitted successfully."
				messages.success(request, success_message)

				return redirect('surveys:survey_properties',
					survey.link_address)
			else:
				error_message = "A 'Survey Report' has been submitted already."
				messages.error(request, error_message)

				return redirect('surveys:survey_properties',
					survey.link_address)
		else:
			error_message = "You must provide a valid report \
				(at least 20 Characters sentence)."
			messages.error(request, error_message)

			return redirect('surveys:survey_properties',
				survey.link_address)
	return redirect('surveys:survey_properties', survey.link_address)


class ResponseSurveyReport(LoginRequiredMixin, generic.DetailView):
	model = Response
	context_object_name = 'response'
	template_name = 'surveys/survey_report_view.html'

	def get_queryset(self):
		return Response.objects.all()

@csrf_protect
@login_required
def survey_report_view(request, id):
	user = get_object_or_404(MyUser, email=request.user.email)

	response = get_object_or_404(Response,
			pk=request.POST.get('id', ''),
		)
	if not user == response.user:
		error_message = "You are not authorized to view this \
		'Response' or its 'Survey Report'."
		messages.error(request, error_message)

		return redirect('surveys')
	if request.method == "POST":		

		if len(str(request.POST['report'])) >= 20:
			if not survey.report:
				survey.report = request.POST['report'] + "\n\n{}: {}".format(
					"Report Date/Time",
					timezone.now()
				)
				survey.save()

				success_message = "Your 'Survey Report' was \
					submitted successfully."
				messages.success(request, success_message)

				return redirect('surveys:survey_properties',
					survey.link_address)
			else:
				error_message = "A 'Survey Report' has been submitted already."
				messages.error(request, error_message)

				return redirect('surveys:survey_properties',
					survey.link_address)
		else:
			error_message = "You must provide a valid report \
				(at least 20 Characters sentence)."
			messages.error(request, error_message)

			return redirect('surveys:survey_properties',
				survey.link_address)
	return redirect('surveys:survey_properties', survey.link_address)


@csrf_protect
@login_required
def preview(request, link_address):
	try:
		survey = get_object_or_404(Survey, pk=link_address)
	except:
		return HttpResponse("Invalid link address")

	if not request.user.email == survey.user.email:
		return HttpResponse("You are not authorized to view this page.")

	survey.survey_properties
	if survey.surveyproperties.published:
		survey_timer = timezone.now() + timedelta(
					minutes=survey.surveyproperties.survey_timer)
	else:
		survey_timer = timezone.now() + timedelta(
					minutes=3)

	""" Session based survey-timer for keeping track of survey-timer
	request.session['survey_timer'] = str(survey_timer)

	session_timer = pd.to_datetime(request.session.get(
		'survey_timer')).to_pydatetime()"""

	formatted_timer = survey_timer.strftime('%Y/%m/%d %H:%M:%S')

	template_name = "surveys/survey_preview.html"
	context = {
		'survey': survey,
		'server_timer': formatted_timer,
	}

	return render(request, template_name, context)

def viewpage(request, link_address):
	try:
		survey = get_object_or_404(Survey, pk=link_address)
	except:
		return HttpResponse("Invalid link address")

	# Check whether survey is published (Opened for responses).
	survey.survey_properties
	if survey.surveyproperties.published:
		pass
	else:
		return HttpResponse('Not published yet')

	# Set this survey as the recent survey.
	request.session['recent_survey'] = str(link_address)


	survey_timer = timezone.now() + timedelta(
					minutes=survey.surveyproperties.survey_timer)

	# Set the survey timer(time required to complete the survey).
	request.session['survey_timer'] = str(survey_timer)

	if request.user.is_authenticated:
		if survey.survey_option == 'P': # Check whether survey has the 'PAID' option.
			user = get_object_or_404(MyUser, email=request.user.email)
			user.response_timer
			utime = user.responsetimer
			# Check whether user can respond to the survey based on the response timer
			if utime.end_time and (utime.end_time > timezone.now()):
				return redirect('surveys:survey_options')
		return redirect('surveys:survey', survey.link_address)
	else:
		return redirect('surveys:asurvey', survey.link_address)


@csrf_protect
@login_required
def survey_options(request):
	user = get_object_or_404(MyUser, email=request.user.email)

	paid_surveys = Survey.objects.filter(survey_option='P'
		).filter(surveyproperties__published=True
		).exclude(completed=True
		).exclude(response__user=user
		).exclude(user=user).order_by('?')[:10]

	free_surveys = Survey.objects.filter(survey_option='F'
		).filter(surveyproperties__published=True
		).exclude(completed=True
		).exclude(response__user=user
		).exclude(user=user).order_by('?')[:10]

	user.response_timer
	user_timer = user.responsetimer.end_time
	formatted_timer = user_timer.strftime('%Y/%m/%d %H:%M:%S')

	context = {
		'paid_surveys': paid_surveys,
		'free_surveys': free_surveys,
		'server_timer': formatted_timer,
	}

	return render(request, 'surveys/survey_options.html', context)


'''@csrf_protect
@login_required
def paid_surveys(request):
	user = get_object_or_404(MyUser, email=request.user.email)

	paid_surveys = Survey.objects.filter(survey_option='P'
		).filter(surveyproperties__published=True
		).exclude(completed=True
		).exclude(response__user=user
		).exclude(user=user).order_by('?')[:10]

	free_surveys = Survey.objects.filter(survey_option='F'
		).filter(surveyproperties__published=True
		).exclude(completed=True
		).exclude(response__user=user
		).exclude(user=user).order_by('?')[:10]

	"""p_surveys = user.surveynotification_set.filter(survey__survey_option='P'
					).exclude(expire_date__lt=timezone.now()).exclude(
					survey__completed=True).exclude(survey__user=user).exclude(
					survey__response__user=user)[:2]"""

	context = {'surveys': surveys}

	return render(request, 'surveys/published_surveys.html', context)


@csrf_protect
@login_required
def free_surveys(request):
	user = get_object_or_404(MyUser, email=request.user.email)

	surveys = Survey.objects.filter(survey_option='F'
		).filter(surveyproperties__published=True
		).exclude(completed=True
		).exclude(response__user=user
		).exclude(user=user).order_by('?')[:10]
	"""f_surveys = user.surveynotification_set.filter(survey__survey_option='F'
					).exclude(expire_date__lt=timezone.now()).exclude(
					survey__completed=True).exclude(survey__user=user).exclude(
					survey__response__user=user)[:1]"""

	context = {'surveys': surveys}

	return render(request, 'surveys/published_surveys.html', context)'''


def anonymous_respond(request, link_address):
	try:
		survey = get_object_or_404(Survey, pk=link_address)
	except:
		return HttpResponse('Invalid link address')

	if request.method == "POST":
		# Retrieve the link address of the survey recently responded to.
		# If no recent survey, make this one the recent one.
		recent_survey = request.session.get('recent_survey',
				str(link_address))

		#Calculate the minimum time required to complete the survey.
		survey_timer = timezone.now() + timedelta(
					minutes=survey.surveyproperties.survey_timer)

		# If the recently responded to survey is not the same as the current one.
		if False: #New Test (not recent_survey == str(link_address):)
			# If the current survey is not the previous survey, set new 'survey timer'.
			request.session['survey_timer'] = str(survey_timer)

		# Get session 'survey timer' string and convert to datetime object type.
		timer = pd.to_datetime(request.session.get(
			'survey_timer', str(survey_timer))).to_pydatetime()

		# Make timer object timezone aware.
		localized_time = tz.utc.localize(timer)

		# If 'survey timer' is not completed; prevent 'Respondent' from submitting response.
		if timezone.now() <= localized_time:
			note = "Survey timer not completed, Please read through survey."
			messages.error(request, note)

			form = RespondentRegisterForm
			formatted_timer = localized_time.strftime('%Y/%m/%d %H:%M:%S')

			context = {
				'survey': survey,
				'server_timer': formatted_timer,
				'form': form,
			}
			return render(request, "surveys/survey_view.html", context)

		if request.POST["submit_option"] == 'u': # If 'Register & Submit' was selected.
			# Check whether the input 'email' is already in use on the site.
			if MyUser.objects.filter(email=request.POST["email"]).exists():
				return HttpResponse("Email already in use!!!, Change It!")

			# Check whether the two password inputs match.
			password = request.POST['password']
			confirm_password = request.POST['confirm_password']
			if password != confirm_password:
				return HttpResponse("password mismatch")

			# Create an 'inactive' user's account for the Respondent.
			user = MyUser.objects.create(
					email=request.POST['email'],
					gender=request.POST['gender'],
					age=request.POST['age'],
					location=request.POST['location'],
					institute=request.POST['institute']
				)
			user.set_password(request.POST['password'])
			user.is_active = False
			user.save()
			user.response_timer
			user.responsetimer.end_time = timezone.now()
			user.responsetimer.save()

			respondent_group = Group.objects.get(name='Respondent')
			respondent_group.user_set.add(user)

			mail_subject = 'Activate your TESIZ Respondent account.'

			send_user_activation_link(request, user, mail_subject)

			success_message = "Your Respondent account was created successfully."
			messages.success(request, success_message)
			#Set the 'status' based on the user's account status(False); inactive status disable verified responses.
			status = user.is_active

		elif request.POST['submit_option'] == 'r': # If 'Submit by R Code' was selected.
			user = None # Not a user; 'Anonymous User'
			status = True # Set the 'status' to 'True'; "R Code's" enable verified responses

			#Check whether the input 'R Code' matches the required 'R Code' for the survey.
			if not survey.surveyproperties.r_code == request.POST['r_code']:
				return HttpResponse("Invalid R Code")

		# Set the 'current survey' as the 'recent survey' session.
		request.session['recent_survey'] = str(link_address)

		# Create 'Response' object for this anonymous response and save it to the database.
		user_response = Response(
			user=user,
			survey=survey,
			resp_date=timezone.now(),
			survey_title=survey.title,
			survey_description=survey.description,
			survey_field=survey.field,
			survey_option=survey.survey_option,
			verified=status
		)
		user_response.save()

		for question in survey.surveyquestion_set.all():
			response_question = ResponseQuestion(response=user_response,
								survey_question=question,
								question_text=question.question_text,
								html_name=question.html_name)
			response_question.save()

			if question.html_name[-2] == 'r':
				try:
					selected_choice = question.surveychoice_set.get(
						pk=request.POST['choice{}'.format(question.id)])
				except (KeyError, SurveyChoice.DoesNotExist):
					error_message = "Incomplete form, fill empty spaces"
					messages.error(request, error_message)

					return render(request, 'surveys/survey_view.html', 
						{'survey': survey})
				else:
					response_choice = ResponseChoice(
								response_question=response_question,
								choice_text=selected_choice.choice_text,
								html_name=selected_choice.html_name)
					response_choice.save()
					selected_choice.votes = F('votes') + 1
					selected_choice.save()

			elif question.html_name[-2] == 't':
				response_choice = ResponseChoice(
						response_question=response_question,
						choice_text=request.POST[
							'choice{}'.format(question.id)],
						html_name='p_{}_t1'.format(question.html_name[2])
					)
				response_choice.save()

			else:
				selected_choices = request.POST.getlist(
					'choice{}'.format(question.id))
				for selected_choice_str in selected_choices:#All question's (checkbox) choices that were selected
					selected_choice = question.surveychoice_set.get(
						pk=selected_choice_str)
					response_choice = ResponseChoice(
								response_question=response_question,
								choice_text=selected_choice.choice_text,
								html_name=selected_choice.html_name)
					response_choice.save()
					selected_choice.votes = F('votes') + 1
					selected_choice.save()

		survey.total_responses = F('total_responses') + 1
		if request.POST['submit_option'] == 'r':
			survey.verified_responses = F('verified_responses') + 1
		survey.save()
		survey.refresh_from_db()

		if survey.verified_responses >= int(survey.sample_size):
			survey.completed = True

		survey.percent_completed = \
			(survey.verified_responses/survey.sample_size) * 100

		survey.save()

		del request.session['recent_survey']
		del request.session['survey_timer']

		success_message = "Your 'Response' was recorded successfully."
		messages.success(request, success_message)

		return redirect('users:login')

	return redirect('surveys:view_page', link_address)

@csrf_protect
@login_required
def user_respond(request, link_address):
	try:
		survey = get_object_or_404(Survey, pk=link_address)
	except:
		return HttpResponse('Invalid link address')
	if request.method == "POST":
		email = request.user.email
		user = get_object_or_404(MyUser, email=email)

		user.response_timer # Retrieves or Creates user response timer instance
		utime = user.responsetimer

		if survey.survey_option == 'P': # Check whether survey has the 'PAID' option.
			# Check whether user can respond to the survey based on the response timer
			if utime.end_time and (utime.end_time > timezone.now()):
				return redirect('surveys:survey_options')

		# Check whether survey was created by the user.
		if survey.user == user:
			return HttpResponse("Unable to process your Response!!")

		# Check whether user has responded to survey before.
		responded = Response.objects.filter(user=user
				).filter(survey=survey).exists()
		if responded:
			return HttpResponse("You can't answer this survey again")

		if survey.completed: # Check whether survey is completed(Has received required responses)
			return HttpResponse("Survey completed. Additional Responses denied")

		# Retrieve the link address of the survey recently responded to.
		# If no recent survey, make this one the recent one.
		recent_survey = request.session.get('recent_survey',
				str(link_address))

		#Calculate the minimum time required to complete the survey.
		survey_timer = timezone.now() + timedelta(
					minutes=survey.surveyproperties.survey_timer)

		# If the recently responded to survey is not the same as the current one.
		if False: #New Test (not recent_survey == str(link_address):)
			# If the current survey is not the previous survey, set new 'survey timer'.
			request.session['survey_timer'] = str(survey_timer)

		# Get session 'survey timer' string and convert to datetime object type.
		timer = pd.to_datetime(request.session.get(
			'survey_timer', str(survey_timer))).to_pydatetime()

		# Make timer object timezone aware.
		localized_time = tz.utc.localize(timer)
		# If 'survey timer' is not completed; prevent 'Respondent' from submitting response.
		if timezone.now() <= localized_time:
			note = "Survey timer not completed, Please read through survey."
			messages.error(request, note)

			formatted_timer = localized_time.strftime('%Y/%m/%d %H:%M:%S')

			context = {
				'survey': survey,
				'server_timer': formatted_timer,
			}
			return render(request, "surveys/survey_view.html", context)

		# Set the 'current survey' as the 'recent survey' session.
		request.session['recent_survey'] = str(link_address)
		
		# Create 'Response' object for this user response and save it to the database.
		user_response = Response(
			user=user,
			survey=survey,
			resp_date=timezone.now(),
			survey_title=survey.title,
			survey_description=survey.description,
			survey_field=survey.field,
			survey_option=survey.survey_option,
			verified=user.is_active
		)
		user_response.save()

		# Update the waiting time(30 minutes) for the user's next 'PAID Survey' response.
		utime.end_time = timezone.now() + timedelta(minutes=30)
		utime.save()


		for question in survey.surveyquestion_set.all():
			response_question = ResponseQuestion(response=user_response,
								survey_question=question,
								question_text=question.question_text,
								html_name=question.html_name)
			response_question.save()

			if question.html_name[-2] == 'r':
				try:
					selected_choice = question.surveychoice_set.get(
						pk=request.POST['choice{}'.format(question.id)])
				except (KeyError, SurveyChoice.DoesNotExist):
					error_message = "Incomplete form, fill empty spaces"
					messages.error(request, error_message)

					return render(request, 'surveys/survey_view.html', 
						{'survey': survey})
				else:
					response_choice = ResponseChoice(
								response_question=response_question,
								choice_text=selected_choice.choice_text,
								html_name=selected_choice.html_name)
					response_choice.save()
					selected_choice.votes = F('votes') + 1
					selected_choice.save()

			elif question.html_name[-2] == 't':
				response_choice = ResponseChoice(
						response_question=response_question,
						choice_text=request.POST[
							'choice{}'.format(question.id)],
						html_name='p_{}_t1'.format(question.html_name[2])
					)
				response_choice.save()

			else:
				selected_choices = request.POST.getlist(
					'choice{}'.format(question.id))
				for selected_choice_str in selected_choices:#All question's (checkbox) choices that were selected
					selected_choice = question.surveychoice_set.get(
						pk=selected_choice_str)
					response_choice = ResponseChoice(
								response_question=response_question,
								choice_text=selected_choice.choice_text,
								html_name=selected_choice.html_name)
					response_choice.save()
					selected_choice.votes = F('votes') + 1
					selected_choice.save()

		survey.total_responses = F('total_responses') + 1
		survey.verified_responses = F('verified_responses') + 1
		survey.save()
		survey.refresh_from_db()

		if survey.verified_responses >= int(survey.sample_size):
			survey.completed = True

		survey.percent_completed = \
			(survey.verified_responses/survey.sample_size) * 100

		survey.save()

		if survey.survey_option == 'P':
			reward_prices = {5:2, 12:8, 20:15}

			if user.survey_offer and user.surveyoffer.on_offer:
				offer_info = user.surveyoffer
				offer_info.progress_count = F('progress_count') + 1
				offer_info.save()
				offer_info.refresh_from_db()

				if offer_info.progress_count >= offer_info.offer_threshold:
					survey_offer_record = SurveyOfferRecords(
							user=user,
							offer_name=offer_info.offer_name,
							offer_threshold=offer_info.offer_threshold,
							completed=True,
							date_started=offer_info.date_started,
							date_ended=timezone.now(),
						)
					reward = Reward(
							user=user,
							reward_name=offer_info.offer_name,
							reward_date=timezone.now(),
							expire_date=timezone.today(),
							reward_price=reward_prices[
								offer_info.offer_threshold]
						)
					offer_info.offer_name=None
					offer_info.progress_count = 0
					offer_info.on_offer = False
					offer_info.offer_threshold = None
					offer_info.date_started = None
					offer_info.expire_date = None

					survey_offer_record.save()
					reward.save()
					offer_info.save()

		del request.session['recent_survey']
		del request.session['survey_timer']

		success_message = "Your 'Response' was recorded successfully."
		messages.success(request, success_message)

		return redirect('surveys:response', user_response.id)

	return redirect('surveys:view_page', link_address)

@csrf_protect
@login_required
def response(request, link_address):
	survey = get_object_or_404(Survey, pk=link_address)
	email = request.user.email
	user = get_object_or_404(MyUser, email=email)

	if not request.user == survey.user:
		return HttpResponse("You are not authorized to have access.")

	all_answers = np.array([]) # Accumulates responses of all respondents in multiple rows on multiple questions basis.
	#row_answers = np.array([])
	column = 1 # Keeps track of the current question's(set of responses by individual respondents) number.
	questions_row = np.array(['Response Date']) # Records a header of questions text in row format.

	if not survey.response_set.filter(verified=True): # If there are no verified responses.
			return HttpResponse('There are no verified responses yet') # Return this message

	"""An algorithm to compile all questions and responses with their timestamps for the current survey"""
	for question in survey.surveyquestion_set.all(): # A sequence of all the questions in the survey.
		time_row = np.array([]) # Keeps records of the timestamps for all responses to the survey
		row_answers = np.array([]) # Accumulates responses of all respondents in multiple rows on per question basis.
		response_question_num = 1 # A variable to keep track of the current 'response question' number.
		number_of_choices = question.surveychoice_set.count() # Returns the number of choices for a question
		choice_status = np.array([]) # Keeps records of selected choices as 'yes', and 'no' for unselected choices

		if question.html_name[-2] == 'c': # If the question is a CheckBox question, add 'question text_choice text'
			for choice in question.surveychoice_set.all():
				questions_row = np.append(
						questions_row,
						'{}_{}'.format(question.question_text,
							choice.choice_text)
					)
		else: # If the question is a RadioButton question, add only its question's text
			questions_row = np.append(
					questions_row,
					question.question_text
				)
		for choice in range(number_of_choices): # Populates a list of "no's" for questions(particularly checkbox ones)
			choice_status = np.append(choice_status, 'no')

		for response_question in question.responsequestion_set.filter(response__verified=True):
			next_row = np.array([]) # Keeps records of each response of a respondent in a row.
			if response_question.html_name[-2] == 'c': # If Response Question is a CheckBox question
				for choice in response_question.responsechoice_set.all():
						choice_status[int(choice.html_name[-1]) - 1] = 'yes' # Set selected choices to 'yes'
				next_row = np.append(next_row, choice_status) # Record question's selected and unselected choices set.

				for choice in response_question.responsechoice_set.all(): # Reset all choices to 'no'
						choice_status[int(choice.html_name[-1]) - 1] = 'no'
			else: # If Response Question is a RadioButton question
				for choice in response_question.responsechoice_set.all():
					next_row = np.append(next_row, choice.choice_text) # Record question's selected choice.

			if response_question_num == 1: # If first question response, initialize a first row of timestamp & selected choice(s).
				time_row = np.vstack(
						(str(response_question.response.resp_date),)
					)
				row_answers = np.vstack(
						(next_row,)
					)
			else: # Otherwise, add the next row of timestamp and selected choice(s)
				time_row = np.vstack(
								(time_row,
								str(response_question.response.resp_date),)
							)
				row_answers = np.vstack(
						(row_answers,
						 next_row,)
					)

			response_question_num += 1
		if column != 1: # If is not the first question responses, add the next question response set to current responses.
				all_answers = np.column_stack(
					(all_answers,
					 row_answers)
					)
		else: # Otherwise, initialize all responses list with the first question response set.
			all_answers = row_answers
			column += 1

	answers_list = np.hstack(
					(time_row,
					 all_answers,)
					 ) # Maps all respondents responses to their response date.
	questions_n_answers = np.vstack(
								(questions_row,
								answers_list)
							) # Add Timestamps and choices titles as header row.
	responses_array = questions_n_answers.tolist()
	print(responses_array)

	title = survey.title
	#build and store the file
	def write_csv():
	    path = settings.MEDIA_ROOT + '/' + email.lower() + '_' + title.lower()
	    path = path.replace('.', '_')
	    path = path.replace(' ', '_') + '.csv'

	    with open(path, 'w') as f:
	    	# wipe the existing content
	    	f.truncate()

	    	csv_writer = csv.writer(f)

	    	for row in responses_array:
	    		csv_writer.writerow(row)

	    	survey.data.name = path
	    	survey.save()
	write_csv()

	return redirect('surveys:download', survey.link_address)


#serve it up as a download
@csrf_protect
@login_required
def get_data(request, link_address):
	survey = get_object_or_404(Survey, pk=link_address)

	if not request.user == survey.user:
		return HttpResponse("You are not authorized to have access.")

	response = HttpResponse(survey.data, content_type='text/csv')
	response['Content-Disposition'] = 'attachment; filename="{}{}"'.format(
		str(survey.title).replace(' ', '_'), '.csv')

	return response
