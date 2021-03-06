# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import json

from django.core.urlresolvers import reverse
from django.test import TestCase

from wagtail.tests.testapp.models import FormField, FormPage
from wagtail.tests.utils import WagtailTestUtils
from wagtail.wagtailadmin.edit_handlers import get_form_for_model
from wagtail.wagtailadmin.forms import WagtailAdminPageForm
from wagtail.wagtailcore.models import Page
from wagtail.wagtailforms.edit_handlers import FormSubmissionsPanel
from wagtail.wagtailforms.models import FormSubmission
from wagtail.wagtailforms.tests.utils import make_form_page


class TestFormResponsesPanel(TestCase):
    def setUp(self):
        self.form_page = make_form_page()

        self.FormPageForm = get_form_for_model(
            FormPage, form_class=WagtailAdminPageForm
        )

        submissions_panel = FormSubmissionsPanel().bind_to_model(FormPage)

        self.panel = submissions_panel(self.form_page, self.FormPageForm())

    def test_render_with_submissions(self):
        """Show the panel with the count of submission and a link to the list_submissions view."""
        self.client.post('/contact-us/', {
            'your-email': 'bob@example.com',
            'your-message': 'hello world',
            'your-choices': {'foo': '', 'bar': '', 'baz': ''}
        })

        result = self.panel.render()

        url = reverse('wagtailforms:list_submissions', args=(self.form_page.id,))
        link = '<a href="{}">1</a>'.format(url)

        self.assertIn(link, result)

    def test_render_without_submissions(self):
        """The panel should not be shown if the number of submission is zero."""
        result = self.panel.render()

        self.assertEqual('', result)


class TestFormsIndex(TestCase):
    fixtures = ['test.json']

    def setUp(self):
        self.assertTrue(self.client.login(username='siteeditor', password='password'))
        self.form_page = Page.objects.get(url_path='/home/contact-us/')

    def make_form_pages(self):
        """
        This makes 100 form pages and adds them as children to 'contact-us'
        This is used to test pagination on the forms index
        """
        for i in range(100):
            self.form_page.add_child(instance=FormPage(
                title="Form " + str(i),
                slug='form-' + str(i),
                live=True
            ))

    def test_forms_index(self):
        response = self.client.get(reverse('wagtailforms:index'))

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index.html')

    def test_forms_index_pagination(self):
        # Create some more form pages to make pagination kick in
        self.make_form_pages()

        # Get page two
        response = self.client.get(reverse('wagtailforms:index'), {'p': 2})

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index.html')

        # Check that we got the correct page
        self.assertEqual(response.context['form_pages'].number, 2)

    def test_forms_index_pagination_invalid(self):
        # Create some more form pages to make pagination kick in
        self.make_form_pages()

        # Get page two
        response = self.client.get(reverse('wagtailforms:index'), {'p': 'Hello world!'})

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index.html')

        # Check that it got page one
        self.assertEqual(response.context['form_pages'].number, 1)

    def test_forms_index_pagination_out_of_range(self):
        # Create some more form pages to make pagination kick in
        self.make_form_pages()

        # Get page two
        response = self.client.get(reverse('wagtailforms:index'), {'p': 99999})

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index.html')

        # Check that it got the last page
        self.assertEqual(response.context['form_pages'].number, response.context['form_pages'].paginator.num_pages)

    def test_cannot_see_forms_without_permission(self):
        # Login with as a user without permission to see forms
        self.assertTrue(self.client.login(username='eventeditor', password='password'))

        response = self.client.get(reverse('wagtailforms:index'))

        # Check that the user cannot see the form page
        self.assertFalse(self.form_page in response.context['form_pages'])

    def test_can_see_forms_with_permission(self):
        response = self.client.get(reverse('wagtailforms:index'))

        # Check that the user can see the form page
        self.assertIn(self.form_page, response.context['form_pages'])


# TODO: Rename to TestFormsSubmissionsList
class TestFormsSubmissions(TestCase, WagtailTestUtils):
    def setUp(self):
        # Create a form page
        self.form_page = make_form_page()

        # Add a couple of form submissions
        old_form_submission = FormSubmission.objects.create(
            page=self.form_page,
            form_data=json.dumps({
                'your-email': "old@example.com",
                'your-message': "this is a really old message",
            }),
        )
        old_form_submission.submit_time = '2013-01-01T12:00:00.000Z'
        old_form_submission.save()

        new_form_submission = FormSubmission.objects.create(
            page=self.form_page,
            form_data=json.dumps({
                'your-email': "new@example.com",
                'your-message': "this is a fairly new message",
            }),
        )
        new_form_submission.submit_time = '2014-01-01T12:00:00.000Z'
        new_form_submission.save()

        # Login
        self.login()

    def make_list_submissions(self):
        """
        This makes 100 submissions to test pagination on the forms submissions page
        """
        for i in range(100):
            submission = FormSubmission(
                page=self.form_page,
                form_data=json.dumps({
                    'hello': 'world'
                })
            )
            submission.save()

    def test_list_submissions(self):
        response = self.client.get(reverse('wagtailforms:list_submissions', args=(self.form_page.id,)))

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index_submissions.html')
        self.assertEqual(len(response.context['data_rows']), 2)

    def test_list_submissions_filtering_date_from(self):
        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id,)), {'date_from': '01/01/2014'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index_submissions.html')
        self.assertEqual(len(response.context['data_rows']), 1)

    def test_list_submissions_filtering_date_to(self):
        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id, )), {'date_to': '12/31/2013'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index_submissions.html')
        self.assertEqual(len(response.context['data_rows']), 1)

    def test_list_submissions_filtering_range(self):
        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id, )),
            {'date_from': '12/31/2013', 'date_to': '01/02/2014'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index_submissions.html')
        self.assertEqual(len(response.context['data_rows']), 1)

    def test_list_submissions_pagination(self):
        self.make_list_submissions()

        response = self.client.get(reverse('wagtailforms:list_submissions', args=(self.form_page.id,)), {'p': 2})

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index_submissions.html')

        # Check that we got the correct page
        self.assertEqual(response.context['submissions'].number, 2)

    def test_list_submissions_pagination_invalid(self):
        self.make_list_submissions()

        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id,)), {'p': 'Hello World!'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index_submissions.html')

        # Check that we got page one
        self.assertEqual(response.context['submissions'].number, 1)

    def test_list_submissions_pagination_out_of_range(self):
        self.make_list_submissions()

        response = self.client.get(reverse('wagtailforms:list_submissions', args=(self.form_page.id,)), {'p': 99999})

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailforms/index_submissions.html')

        # Check that we got the last page
        self.assertEqual(response.context['submissions'].number, response.context['submissions'].paginator.num_pages)

    def test_list_submissions_csv_export(self):
        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id,)),
            {'action': 'CSV'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        data_lines = response.content.decode().split("\n")

        self.assertEqual(data_lines[0], 'Submission date,Your email,Your message,Your choices\r')
        self.assertEqual(data_lines[1], '2013-01-01 12:00:00+00:00,old@example.com,this is a really old message,None\r')
        self.assertEqual(data_lines[2], '2014-01-01 12:00:00+00:00,new@example.com,this is a fairly new message,None\r')

    def test_list_submissions_csv_export_with_date_from_filtering(self):
        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id,)),
            {'action': 'CSV', 'date_from': '01/01/2014'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        data_lines = response.content.decode().split("\n")

        self.assertEqual(data_lines[0], 'Submission date,Your email,Your message,Your choices\r')
        self.assertEqual(data_lines[1], '2014-01-01 12:00:00+00:00,new@example.com,this is a fairly new message,None\r')

    def test_list_submissions_csv_export_with_date_to_filtering(self):
        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id,)),
            {'action': 'CSV', 'date_to': '12/31/2013'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        data_lines = response.content.decode().split("\n")

        self.assertEqual(data_lines[0], 'Submission date,Your email,Your message,Your choices\r')
        self.assertEqual(data_lines[1], '2013-01-01 12:00:00+00:00,old@example.com,this is a really old message,None\r')

    def test_list_submissions_csv_export_with_range_filtering(self):
        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id,)),
            {'action': 'CSV', 'date_from': '12/31/2013', 'date_to': '01/02/2014'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        data_lines = response.content.decode().split("\n")

        self.assertEqual(data_lines[0], 'Submission date,Your email,Your message,Your choices\r')
        self.assertEqual(data_lines[1], '2014-01-01 12:00:00+00:00,new@example.com,this is a fairly new message,None\r')

    def test_list_submissions_csv_export_with_unicode_in_submission(self):
        unicode_form_submission = FormSubmission.objects.create(
            page=self.form_page,
            form_data=json.dumps({
                'your-email': "unicode@example.com",
                'your-message': 'こんにちは、世界',
            }),
        )
        unicode_form_submission.submit_time = '2014-01-02T12:00:00.000Z'
        unicode_form_submission.save()

        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id,)),
            {'date_from': '01/02/2014', 'action': 'CSV'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        data_line = response.content.decode('utf-8').split("\n")[1]
        self.assertIn('こんにちは、世界', data_line)

    def test_list_submissions_csv_export_with_unicode_in_field(self):
        FormField.objects.create(
            page=self.form_page,
            sort_order=2,
            label="Выберите самую любимую IDE для разработке на Python",
            help_text="Вы можете выбрать только один вариант",
            field_type='radio',
            required=True,
            choices='PyCharm,vim,nano',
        )
        unicode_form_submission = FormSubmission.objects.create(
            page=self.form_page,
            form_data=json.dumps({
                'your-email': "unicode@example.com",
                'your-message': "We don\'t need unicode here",
                'vyberite-samuiu-liubimuiu-ide-dlia-razrabotke-na-python': "vim",
            }),
        )
        unicode_form_submission.submit_time = '2014-01-02T12:00:00.000Z'
        unicode_form_submission.save()

        response = self.client.get(
            reverse('wagtailforms:list_submissions', args=(self.form_page.id, )),
            {'date_from': '01/02/2014', 'action': 'CSV'}
        )

        # Check response
        self.assertEqual(response.status_code, 200)

        data_lines = response.content.decode('utf-8').split("\n")
        self.assertIn('Выберите самую любимую IDE для разработке на Python', data_lines[0])
        self.assertIn('vim', data_lines[1])


# TODO: add TestCustomFormsSubmissionsList


class TestDeleteFormSubmission(TestCase):
    fixtures = ['test.json']

    def setUp(self):
        self.assertTrue(self.client.login(username='siteeditor', password='password'))
        self.form_page = Page.objects.get(url_path='/home/contact-us/')

    def test_delete_submission_show_cofirmation(self):
        response = self.client.get(reverse(
            'wagtailforms:delete_submission',
            args=(self.form_page.id, FormSubmission.objects.first().id)
        ))
        # Check show confirm page when HTTP method is GET
        self.assertTemplateUsed(response, 'wagtailforms/confirm_delete.html')

        # Check that the deletion has not happened with GET request
        self.assertEqual(FormSubmission.objects.count(), 2)

    def test_delete_submission_with_permissions(self):
        response = self.client.post(reverse(
            'wagtailforms:delete_submission',
            args=(self.form_page.id, FormSubmission.objects.first().id)
        ))

        # Check that the submission is gone
        self.assertEqual(FormSubmission.objects.count(), 1)
        # Should be redirected to list of submissions
        self.assertRedirects(response, reverse("wagtailforms:list_submissions", args=(self.form_page.id,)))

    def test_delete_submission_bad_permissions(self):
        self.assertTrue(self.client.login(username="eventeditor", password="password"))

        response = self.client.post(reverse(
            'wagtailforms:delete_submission',
            args=(self.form_page.id, FormSubmission.objects.first().id)
        ))

        # Check that the user recieved a 403 response
        self.assertEqual(response.status_code, 403)

        # Check that the deletion has not happened
        self.assertEqual(FormSubmission.objects.count(), 2)


# TODO: add TestDeleteCustomFormSubmission


class TestIssue585(TestCase):
    fixtures = ['test.json']

    def setUp(self):

        self.assertTrue(self.client.login(username='superuser', password='password'))
        # Find root page
        self.root_page = Page.objects.get(id=2)

    def test_adding_duplicate_form_labels(self):
        post_data = {
            'title': "Form page!",
            'content': "Some content",
            'slug': 'contact-us',
            'form_fields-TOTAL_FORMS': '3',
            'form_fields-INITIAL_FORMS': '3',
            'form_fields-MIN_NUM_FORMS': '0',
            'form_fields-MAX_NUM_FORMS': '1000',
            'form_fields-0-id': '',
            'form_fields-0-label': 'foo',
            'form_fields-0-field_type': 'singleline',
            'form_fields-1-id': '',
            'form_fields-1-label': 'foo',
            'form_fields-1-field_type': 'singleline',
            'form_fields-2-id': '',
            'form_fields-2-label': 'bar',
            'form_fields-2-field_type': 'singleline',
        }
        response = self.client.post(
            reverse('wagtailadmin_pages:add', args=('tests', 'formpage', self.root_page.id)), post_data
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            text="There is another field with the label foo, please change one of them.",
        )
