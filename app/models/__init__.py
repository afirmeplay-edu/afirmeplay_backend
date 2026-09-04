from .city import City
from .school import School
from .schoolTeacher import SchoolTeacher
from .schoolCourse import SchoolCourse
from .teacher import Teacher
from .student import Student
from .studentSchoolEnrollment import StudentSchoolEnrollment
from .subject import Subject
from .studentClass import Class
from .classSubject import ClassSubject
from .studentTestOlimpics import StudentTestOlimpics
from app.exams.models import (
    Test,
    TestQuestion,
    Question,
    StudentAnswer,
    TestSession,
    ClassTest,
    SubjectiveTest,
    SubjectiveQuestion,
    SubjectiveResult,
    SubjectivePresence,
)
from .educationStage import EducationStage
from .grades import Grade
from .skill import Skill
from .userQuickLinks import UserQuickLinks
from .teacherClass import TeacherClass
from .user import User
from .game import Game
from app.evaluations.models import EvaluationResult
from .manager import Manager
from app.physical_tests.models import PhysicalTestAnswer, PhysicalTestForm, PhysicalTestZip
from .coverTemplate import CoverTemplate
from .studentPasswordLog import StudentPasswordLog
from .user_settings import UserSettings
from app.reports.models import ReportAggregate
from app.answer_sheets.models import (
    AnswerSheetGabarito,
    AnswerSheetResult,
    AnswerSheetGenerationJob,
    AnswerSheetReportAggregate,
    FormCoordinates,
    BatchCorrectionJob,
)
from app.answer_sheets.services.cartao_resposta.answer_sheet_gabarito_generation import (
    AnswerSheetGabaritoGeneration,
)
from .monitoring_action import MonitoringAction
from .monitoring_action_history import MonitoringActionHistory
from .saved_ata_sala import SavedAtaSala

from app.calendar.models import (
    CalendarEvent,
    CalendarVisibilityScope,
    CalendarEventTarget,
    CalendarTargetType,
    CalendarEventUser,
    CalendarEventResource,
)

# Formulários Socioeconômicos, Play TV e Plantão Online
from app.socioeconomic_forms.models import Form, FormQuestion, FormRecipient, FormResponse
from app.play_tv.models import PlayTvVideo, PlayTvVideoSchool, PlayTvVideoResource
from app.plantao_online.models import PlantaoOnline, PlantaoOnlineSchool

# Certificados
from app.certification.models import CertificateTemplate, Certificate

# Saldo e moedas do aluno
from app.balance.models import StudentCoins, CoinTransaction

# Competições
from app.competitions.models import Competition

# Calculadora de Metas IDEB
from app.ideb_meta.models import IdebMetaSave

# Loja (itens compráveis com afirmecoins)
from app.store.models import StoreItem, StudentPurchase

# Mobile offline-first (tabelas por schema city_*)
from app.mobile.models import (
    MobileDevice,
    MobileOfflinePackCode,
    MobileOfflinePackRedeemDevice,
    MobileSyncBundleGeneration,
    MobileSyncSubmission,
    MobileOfflinePackRegistry,
    MobileCityDirectory,
)