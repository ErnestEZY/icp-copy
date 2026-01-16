from ..config import EMAILJS_PUBLIC_KEY, EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID
import logging

logger = logging.getLogger(__name__)

# Note: send_verification_email has been moved to frontend using EmailJS.
# This file now only handles backend-specific alerts if needed, 
# although EmailJS is preferred for frontend-driven flows.

async def send_admin_alert(subject: str, message: str):
    """
    Sends a security alert email to the admin.
    Note: Currently using placeholder logic as we move to EmailJS.
    """
    from ..config import ADMIN_ALERT_EMAIL
    if not ADMIN_ALERT_EMAIL:
        return False
    
    # In a real scenario, you'd call a backend EmailJS API or similar here
    # For now, we'll just log it.
    logger.warning(f"ADMIN ALERT: {subject} - {message}")
    return True
