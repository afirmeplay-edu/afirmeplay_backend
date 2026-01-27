from .city import City
from .school import School
from .schoolTeacher import SchoolTeacher
from .schoolCourse import SchoolCourse
from .teacher import Teacher
from .student import Student
from .subject import Subject
from .studentClass import Class
from .classSubject import ClassSubject
from .classTest import ClassTest
from .studentTestOlimpics import StudentTestOlimpics
from .test import Test
from .testQuestion import TestQuestion
from .educationStage import EducationStage
from .grades import Grade
from .skill import Skill
from .question import Question
from .studentAnswer import StudentAnswer
from .testSession import TestSession
from .userQuickLinks import UserQuickLinks
from .teacherClass import TeacherClass
from .user import User
from .game import Game
from .evaluationResult import EvaluationResult
from .manager import Manager
from .physicalTestAnswer import PhysicalTestAnswer
from .physicalTestForm import PhysicalTestForm
from .formCoordinates import FormCoordinates
from .studentPasswordLog import StudentPasswordLog
from .user_settings import UserSettings
from .reportAggregate import ReportAggregate
from .answerSheetGabarito import AnswerSheetGabarito
from .answerSheetResult import AnswerSheetResult

from .calendar_event import CalendarEvent, CalendarVisibilityScope
from .calendar_event_target import CalendarEventTarget, CalendarTargetType
from .calendar_event_user import CalendarEventUser

# Formulários Socioeconômicos e Play TV
from app.socioeconomic_forms.models import Form, FormQuestion, FormRecipient, FormResponse
from app.play_tv.models import PlayTvVideo, PlayTvVideoSchool

# Certificados
from app.certification.models import CertificateTemplate, Certificate


