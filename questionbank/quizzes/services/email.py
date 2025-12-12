"""
Email service for sending quiz invitations via Resend.
"""
import resend
from django.conf import settings
from django.utils import timezone


def send_quiz_invitations(quiz, invitations, request=None):
    """
    Send quiz invitation emails to students.

    Args:
        quiz: QuizSession instance
        invitations: List of QuizInvitation instances
        request: Optional HTTP request for building URLs

    Returns:
        dict with sent, failed counts and errors list
    """
    resend.api_key = settings.RESEND_API_KEY

    # Build base URL
    if request:
        base_url = f"{request.scheme}://{request.get_host()}"
    else:
        base_url = getattr(settings, 'BASE_URL', 'https://mkt-production.up.railway.app')

    from_email = getattr(settings, 'FROM_EMAIL', 'quizzes@updates.yourdomain.com')

    sent = 0
    failed = 0
    errors = []

    for invitation in invitations:
        quiz_url = f"{base_url}/quiz/{invitation.code}/"

        try:
            # Build email content
            subject = f"Quiz Invitation: {quiz.name}"

            html_content = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #0284c7;">Quiz Invitation</h2>

                <p>Hello {invitation.student_name or 'Student'},</p>

                <p>You have been invited to take the following quiz:</p>

                <div style="background: #f0f9ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin: 0 0 10px 0; color: #0369a1;">{quiz.name}</h3>
                    {f'<p style="margin: 0; color: #64748b;">{quiz.description}</p>' if quiz.description else ''}
                    <p style="margin: 10px 0 0 0; color: #64748b;">
                        Time limit: {quiz.time_limit_minutes} minutes
                    </p>
                </div>

                <p>Click the button below to start your quiz:</p>

                <a href="{quiz_url}"
                   style="display: inline-block; background: #0284c7; color: white;
                          padding: 12px 24px; text-decoration: none; border-radius: 6px;
                          font-weight: bold; margin: 10px 0;">
                    Start Quiz
                </a>

                <p style="color: #64748b; font-size: 14px; margin-top: 20px;">
                    Or copy this link: <a href="{quiz_url}">{quiz_url}</a>
                </p>

                <p style="color: #94a3b8; font-size: 12px; margin-top: 30px;">
                    This is your personal quiz link. Do not share it with others.
                </p>
            </div>
            """

            text_content = f"""
Quiz Invitation: {quiz.name}

Hello {invitation.student_name or 'Student'},

You have been invited to take the quiz: {quiz.name}

Time limit: {quiz.time_limit_minutes} minutes

Click here to start: {quiz_url}

This is your personal quiz link. Do not share it with others.
            """

            # Send via Resend
            response = resend.Emails.send({
                "from": from_email,
                "to": [invitation.student_email],
                "subject": subject,
                "html": html_content,
                "text": text_content
            })

            # Update invitation
            invitation.email_sent_at = timezone.now()
            invitation.email_error = ''
            invitation.save(update_fields=['email_sent_at', 'email_error'])
            sent += 1

        except Exception as e:
            invitation.email_error = str(e)
            invitation.save(update_fields=['email_error'])
            errors.append(f"{invitation.student_email}: {str(e)}")
            failed += 1

    return {
        'sent': sent,
        'failed': failed,
        'errors': errors
    }
