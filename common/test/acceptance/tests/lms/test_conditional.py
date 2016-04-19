"""
Bok choy acceptance tests for conditionals in the LMS

See also old lettuce tests in lms/djangoapps/courseware/features/conditional.feature
"""
from capa.tests.response_xml_factory import StringResponseXMLFactory
from ..helpers import UniqueCourseTest
from ...fixtures.course import CourseFixture, XBlockFixtureDesc
from ...pages.lms.courseware import CoursewarePage
from ...pages.lms.problem import ProblemPage
from ...pages.studio.auto_auth import AutoAuthPage


class ConditionalTest(UniqueCourseTest):
    """
    Test the conditional module in the lms.
    """

    def setUp(self):
        super(ConditionalTest, self).setUp()

        self.username = 'username'
        self.email = 'username@example.com'
        self.password = 'password'
        self.courseware_page = CoursewarePage(self.browser, self.course_id)
        AutoAuthPage(
            self.browser,
            username=self.username,
            email=self.email,
            password=self.password,
            course_id=self.course_id,
            staff=False
        ).visit()

    def install_course_fixture(self, is_staff=False, block_type='problem'):
        """
        Install a course fixture
        """
        self.course_fixture = CourseFixture(
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run'],
            self.course_info['display_name'],
        )
        self.vertical = XBlockFixtureDesc('vertical', 'Test Unit')
        # populate the course fixture with the right conditional modules
        self.course_fixture.add_children(
            XBlockFixtureDesc('chapter', 'Test Section').add_children(
                XBlockFixtureDesc('sequential', 'Test Subsection').add_children(
                    self.vertical
                )
            )
        )

        # Construct conditional block
        metadata = {}
        source_location = None
        if block_type == 'problem':
            problem_factory = StringResponseXMLFactory()
            problem_xml = problem_factory.build_xml(
                question_text='The answer is "correct string"',
                case_sensitive=False,
                answer='correct string',
            ),
            problem = XBlockFixtureDesc('problem', 'Test Problem', data=problem_xml)
            self.vertical.add_children(problem)
            source_location = problem.locator
            metadata = {
                'attempted': 'True'
            }
        elif block_type == 'poll':
            poll = XBlockFixtureDesc(
                'poll_question',
                'Conditional Poll',
                data={
                    'question': 'Is this a good poll?',
                    'answers': [
                        {'id': 'yes', 'text': 'Yes, of course'},
                        {'id': 'no', 'text': 'Of course not!'}
                    ],
                }
            )
            metadata = {
                'poll_answer': 'yes'
            }
            poll = self.vertical.add_children(poll)
            source_location = poll.locator
        else:
            raise NotImplementedError()

        # create conditional
        conditional = XBlockFixtureDesc(
            'conditional',
            'Test Conditional',
            metadata=metadata,
            sources_list=[source_location]
        )
        result_block = XBlockFixtureDesc(
            'html', 'Conditional Contents',
            data='<html><div class="hidden-contents">Hidden Contents</p></html>'
        )
        self.course_fixture.create_xblock(conditional.locator, result_block)
        self.course_fixture.install()

    def test_conditional_hides_content(self):
        self.install_course_fixture()
        self.courseware_page.visit()
        problem_page = ProblemPage(self.browser)

    def test_conditional_displays_content(self):
        pass

    def test_conditional_handles_polls(self):
        pass
