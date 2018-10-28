import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
#from django.contrib.auth.models import User
#from django.shortcuts import reverse

# Create your models here.
SURVEY_FIELD = (
	('SOCIAL LIFE', 'SOCIAL LIFE'),
	('HEALTH & MEDICINE', 'HEALTH & MEDICINE'),
	('FINANCE & BUSINESS', 'FINANCE & BUSINESS'),
)
SURVEY_OPTION = (
	('F', 'FREE'),
	('P', 'PAID'),
)

class Survey(models.Model):
	link_address = models.UUIDField(primary_key=True, default=uuid.uuid4,
									editable=True)
	user = models.ForeignKey(settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
	 	blank=True,
		null=True,)
	title = models.CharField(max_length=250, default="Untitled Survey")
	description = models.TextField(default="No Description")
	field = models.CharField(max_length=50, choices=SURVEY_FIELD)
	survey_option = models.CharField(max_length=1, choices=SURVEY_OPTION)
	is_paid = models.BooleanField(default=False)
	data = models.FileField(null=True, blank=True)
	sample_size = models.IntegerField()
	total_responses = models.IntegerField(default=0)
	verified_responses = models.IntegerField(default=0)
	date_created = models.DateTimeField(null=True)
	completed = models.BooleanField(default=False)
	percent_completed = models.DecimalField(default=0.0,
				decimal_places=1,
				max_digits=4)
	date_completed = models.DateTimeField(blank=True, null=True)
	report = models.TextField(default="", blank=True)

	def __str__(self):
		return '{}, {}'.format(self.title, self.user)

	class Meta:
		ordering = ['-date_created']


class SurveyProperties(models.Model):
	survey = models.OneToOneField(Survey,
			on_delete=models.CASCADE
		)
	r_code = models.CharField(max_length=4, null=True)
	survey_timer = models.IntegerField(null=True)
	published = models.BooleanField(default=False)
	published_date = models.DateTimeField(null=True)

class SurveyQuestion(models.Model):
	html_name = models.CharField(max_length=6)
	question_number = models.CharField(max_length=1, null=True)
	survey = models.ForeignKey(Survey,
		on_delete=models.SET_NULL,
		blank=True,
		null=True,)
	question_text = models.CharField(max_length=500)

	def __str__(self):
		return self.question_text

	class Meta:
		ordering = ['id']

class SurveyChoice(models.Model):
	html_name = models.CharField(max_length=6)
	choice_number = models.CharField(max_length=1, null=True)
	survey_question = models.ForeignKey(SurveyQuestion, on_delete=models.CASCADE)
	choice_text = models.CharField(max_length=200)
	votes = models.IntegerField(default=0)

	def __str__(self):
		return self.choice_text

	class Meta:
		ordering = ['id']

class Response(models.Model):
	resp_date = models.DateTimeField('Response date')
	user = models.ForeignKey(settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		blank=True,
		null=True,)
	survey = models.ForeignKey(Survey,
		on_delete=models.SET_NULL,
		blank=True,
		null=True,)
	"""Survey details for a Response"""
	survey_title = models.CharField(max_length=250)
	survey_description = models.TextField()
	survey_field = models.CharField(max_length=50, choices=SURVEY_FIELD)
	survey_option = models.CharField(max_length=1, choices=SURVEY_OPTION)
	verified = models.BooleanField(default=False)

	class Meta:
		unique_together = (('user', 'survey'),)
		ordering = ['-id']

	def __str__(self):
		return '{}, {}'.format(self.survey_title, self.user)

class ResponseQuestion(models.Model):
	survey_question = models.ForeignKey(SurveyQuestion,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,)
	response = models.ForeignKey(Response,
		on_delete=models.CASCADE)
	question_text = models.CharField(max_length=500)
	html_name = models.CharField(max_length=6, null=True, blank=True)

	class Meta:
		ordering = ['id']

class ResponseChoice(models.Model):
	choice_text = models.TextField()
	response_question = models.ForeignKey(ResponseQuestion,
		on_delete=models.CASCADE)
	html_name = models.CharField(max_length=6, null=True, blank=True)

	class Meta:
		ordering = ['id']


Survey.survey_properties = property(
        lambda s: SurveyProperties.objects.get_or_create(survey=s)[0]
    )
