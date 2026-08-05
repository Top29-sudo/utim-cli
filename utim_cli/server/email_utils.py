import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger("utim.email")

# ── Shared base template ──────────────────────────────────────────────────────
def _base_template(body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    
    body {{
      background-color: #09090b;
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #a1a1aa;
      padding: 48px 20px;
      -webkit-font-smoothing: antialiased;
      line-height: 1.6;
    }}
    
    .wrapper {{
      max-width: 540px;
      margin: 0 auto;
    }}
    
    /* Header */
    .header {{
      text-align: center;
      margin-bottom: 28px;
    }}
    
    .logo {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.04em;
      color: #ffffff;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    
    .logo-prompt {{
      color: #818cf8;
    }}
    
    .logo-tag {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px;
      letter-spacing: 0.12em;
      color: #6366f1;
      background: rgba(99, 102, 241, 0.1);
      border: 1px solid rgba(99, 102, 241, 0.25);
      border-radius: 9999px;
      padding: 3px 10px;
      text-transform: uppercase;
      font-weight: 600;
      margin-left: 6px;
      vertical-align: middle;
    }}
    
    /* Card */
    .card {{
      background-color: #121215;
      border: 1px solid #27272a;
      border-radius: 16px;
      padding: 40px 36px;
      box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.7);
      position: relative;
      overflow: hidden;
    }}
    
    /* Top vibrant gradient beam */
    .card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
    }}
    
    h1.email-title {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 22px;
      font-weight: 700;
      color: #f4f4f5;
      margin-bottom: 8px;
      letter-spacing: -0.02em;
      line-height: 1.35;
    }}
    
    .divider {{
      border: none;
      border-top: 1px solid #27272a;
      margin: 28px 0;
    }}
    
    p {{
      font-size: 14px;
      margin-bottom: 18px;
      color: #a1a1aa;
      line-height: 1.6;
    }}
    
    p.greeting {{
      font-size: 15px;
      color: #e4e4e7;
      font-weight: 500;
    }}
    
    /* Terminal code block */
    .terminal-window {{
      background: #09090b;
      border: 1px solid #27272a;
      border-radius: 10px;
      margin: 20px 0;
      overflow: hidden;
    }}
    
    .terminal-header {{
      background: #18181b;
      padding: 8px 14px;
      display: flex;
      align-items: center;
      gap: 6px;
      border-bottom: 1px solid #27272a;
    }}
    
    .terminal-dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      display: inline-block;
    }}
    .dot-red {{ background: #ef4444; }}
    .dot-yellow {{ background: #f59e0b; }}
    .dot-green {{ background: #10b981; }}
    
    .terminal-title {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: #71717a;
      margin-left: 6px;
    }}
    
    .code-block {{
      padding: 16px;
      font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 13px;
      color: #f4f4f5;
      line-height: 1.6;
    }}
    
    .code-prompt {{
      color: #a855f7;
      font-weight: 600;
      user-select: none;
    }}
    
    .code-cmd {{
      color: #38bdf8;
    }}
    
    .code-pkg {{
      color: #f4f4f5;
    }}
    
    /* CTA Button */
    .btn {{
      display: inline-block;
      padding: 12px 26px;
      border-radius: 8px;
      font-weight: 600;
      font-size: 13px;
      text-decoration: none;
      text-align: center;
      transition: all 0.2s ease;
    }}
    
    .btn-primary {{
      background-color: #ffffff;
      color: #09090b !important;
      box-shadow: 0 4px 14px rgba(255, 255, 255, 0.15);
    }}
    
    .btn-warning {{
      background-color: #f59e0b;
      color: #09090b !important;
    }}
    
    .btn-danger {{
      background-color: #ef4444;
      color: #ffffff !important;
    }}
    
    /* Status Badge */
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border-radius: 9999px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      margin-bottom: 20px;
    }}
    
    .badge-indigo {{ background: rgba(99, 102, 241, 0.12); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); }}
    .badge-amber {{ background: rgba(245, 158, 11, 0.12); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
    .badge-emerald {{ background: rgba(16, 185, 129, 0.12); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
    .badge-rose {{ background: rgba(244, 63, 94, 0.12); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }}
    
    /* OTP Box */
    .otp-container {{
      background: #09090b;
      border: 1px solid rgba(99, 102, 241, 0.35);
      border-radius: 12px;
      padding: 28px 20px;
      text-align: center;
      margin: 24px 0;
      box-shadow: 0 0 25px rgba(99, 102, 241, 0.08);
    }}
    
    .otp-code {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 38px;
      font-weight: 700;
      letter-spacing: 14px;
      color: #818cf8;
      margin: 8px 0;
      display: inline-block;
      padding-left: 14px;
    }}
    
    .otp-expiry {{
      font-size: 12px;
      color: #71717a;
      margin-top: 8px;
      font-family: 'JetBrains Mono', monospace;
    }}
    
    /* Highlight box */
    .highlight-box {{
      background: #18181b;
      border: 1px solid #27272a;
      border-radius: 12px;
      padding: 24px;
      margin: 24px 0;
      text-align: center;
    }}
    
    .highlight-box .amount {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 30px;
      font-weight: 700;
      color: #f4f4f5;
      line-height: 1.2;
    }}
    
    .highlight-box .amount span {{
      font-size: 14px;
      font-weight: 400;
      color: #71717a;
      margin-left: 6px;
    }}
    
    /* Footer */
    .footer {{
      text-align: center;
      padding: 32px 0 16px;
      font-size: 12px;
      color: #52525b;
    }}
    
    .footer a {{
      color: #71717a;
      text-decoration: none;
    }}
    
    .footer a:hover {{
      color: #a1a1aa;
    }}
    
    .footer .links {{
      margin-bottom: 14px;
    }}
    
    .footer .links a {{
      margin: 0 10px;
    }}
    
    .footer-divider {{
      display: inline-block;
      width: 3px;
      height: 3px;
      border-radius: 50%;
      background: #3f3f46;
      vertical-align: middle;
      margin: 0 4px;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <div class="logo"><span class="logo-prompt">&gt;_</span> UTIM<span class="logo-tag">CLI</span></div>
    </div>
    <div class="card">
      {body_html}
    </div>
    <div class="footer">
      <div class="links">
        <a href="https://utim.dev">utim.dev</a>
        <span class="footer-divider"></span>
        <a href="https://utim.dev/docs">Documentation</a>
        <span class="footer-divider"></span>
        <a href="mailto:support@utim.dev">Support</a>
      </div>
      <p>© 2026 UTIM CLI • Universal Terminal Intelligence Manager</p>
    </div>
  </div>
</body>
</html>"""


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send an email using configured SMTP settings with Brevo HTTP fallback."""
    smtp_host = os.environ.get("SMTP_HOST", "smtp-relay.brevo.com")
    try:
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        smtp_port = 587

    smtp_user = (
        os.environ.get("SMTP_USER") or
        os.environ.get("BREVO_USER") or
        os.environ.get("BREVO_LOGIN") or
        os.environ.get("SMTP_LOGIN") or
        ""
    )
    smtp_password = (
        os.environ.get("SMTP_PASSWORD") or
        os.environ.get("SMTP_KEY") or
        os.environ.get("BREVO_SMTP_KEY") or
        os.environ.get("BREVO_API_KEY") or
        ""
    )
    smtp_from_email = os.environ.get("SMTP_FROM_EMAIL", "support@utim.dev")
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "UTIM CLI")

    if not smtp_user or not smtp_password:
        logger.warning(
            f"SMTP credentials not configured (SMTP_USER={bool(smtp_user)}, SMTP_PASSWORD={bool(smtp_password)}). "
            "Skipping email delivery."
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from_email, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from_email, to_email, msg.as_string())

        logger.info(f"Email sent successfully to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"SMTP email delivery to {to_email} failed ({e}). Trying fallback to Brevo HTTP API...")
        try:
            import requests
            brevo_api_key = (
                os.environ.get("BREVO_API_KEY") or
                os.environ.get("BREVO_API_KEY_V3") or
                os.environ.get("BREVO_KEY") or
                os.environ.get("BREVO_SECRET") or
                os.environ.get("BREVO_API") or
                os.environ.get("API_KEY") or
                smtp_password
            )
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "accept": "application/json",
                "api-key": brevo_api_key,
                "content-type": "application/json"
            }
            payload = {
                "sender": {
                    "name": smtp_from_name,
                    "email": smtp_from_email
                },
                "to": [
                    {
                        "email": to_email
                    }
                ],
                "subject": subject,
                "htmlContent": html_content
            }
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code in (200, 201, 202):
                logger.info(f"Email sent successfully via Brevo HTTP API fallback to {to_email}: {subject}")
                return True
            else:
                logger.error(f"Brevo HTTP API fallback failed with status {res.status_code}: {res.text}")
                return False
        except Exception as exc:
            logger.error(f"Failed to send email to {to_email} via both SMTP and HTTP API: {exc}")
            return False


def send_welcome_email(to_email: str, display_name: str) -> bool:
    """Send a welcoming onboarding email."""
    subject = "Welcome to UTIM CLI — Your Terminal Intelligence Engine 🚀"
    body = f"""
      <div class="badge badge-indigo">● SYSTEM_ONBOARDING</div>
      <h1 class="email-title">Welcome aboard, {display_name}</h1>
      <p class="greeting">You now have access to UTIM's autonomous CLI engine.</p>
      
      <p>
        UTIM provides agentic coding capabilities right inside your terminal — with native
        MCP server orchestration, semantic memory, and complete project awareness.
      </p>
      
      <div class="terminal-window">
        <div class="terminal-header">
          <span class="terminal-dot dot-red"></span>
          <span class="terminal-dot dot-yellow"></span>
          <span class="terminal-dot dot-green"></span>
          <span class="terminal-title">bash — quickstart</span>
        </div>
        <div class="code-block">
          <div><span class="code-prompt">$</span> <span class="code-cmd">npm</span> install -g <span class="code-pkg">@emend-ai/utim</span></div>
          <div style="margin-top: 8px;"><span class="code-prompt">$</span> <span class="code-cmd">utim</span></div>
        </div>
      </div>

      <p>Run <code style="font-family: 'JetBrains Mono', monospace; color: #818cf8; background: rgba(99,102,241,0.1); padding: 2px 6px; border-radius: 4px;">/usage</code> in the CLI anytime to monitor your active session credits and tier quota.</p>
      
      <div style="margin-top: 32px; text-align: left;">
        <a href="https://utim.dev/docs" class="btn btn-primary">Open Documentation &rarr;</a>
      </div>
    """
    return send_email(to_email, subject, _base_template(body))


def send_otp_email(to_email: str, otp_code: str) -> bool:
    """Send a 6-digit OTP verification code email."""
    subject = f"🔐 Your UTIM Verification Code: {otp_code}"
    body = f"""
      <div class="badge badge-indigo">● SECURITY_AUTHENTICATION</div>
      <h1 class="email-title">Verify your identity</h1>
      <p class="greeting">Use the 6-digit security code below to authorize your session:</p>

      <div class="otp-container">
        <div class="otp-code">{otp_code}</div>
        <div class="otp-expiry">⏱ CODE EXPIRES IN 10 MINUTES</div>
      </div>

      <p style="color: #71717a; font-size: 13px;">If you didn't request this code, you can safely disregard this email. Never share your verification code with anyone.</p>
    """
    return send_email(to_email, subject, _base_template(body))


def send_quota_left_email(to_email: str, display_name: str, remaining_percent: float, is_exhausted: bool) -> bool:
    """Send an alert if quota is low or fully exhausted."""
    if is_exhausted:
        subject = "⚠️ Action Required: Your UTIM Quota is Exhausted"
        badge = '<div class="badge badge-rose">● QUOTA_EXHAUSTED</div>'
        title = "Your monthly quota is exhausted"
        desc = (
            "You have reached 100% of your usage limit for this billing cycle. "
            "Agent completions and LLM calls are temporarily paused. "
            "Upgrade your plan or top up to restore instant access."
        )
        btn_class = "btn-danger"
        btn_label = "Upgrade Plan &rarr;"
    else:
        subject = "⚡ Notice: Your UTIM quota is running low"
        badge = '<div class="badge badge-amber">● LOW_QUOTA_WARNING</div>'
        title = "Quota threshold alert"
        desc = (
            f"You have less than <strong style='color:#fbbf24'>{remaining_percent:.1f}%</strong> of your monthly usage allocation remaining. "
            "Top up credits or upgrade to keep your agentic workflows running smoothly."
        )
        btn_class = "btn-warning"
        btn_label = "Refill Credits &rarr;"

    body = f"""
      {badge}
      <h1 class="email-title">{title}</h1>
      <p class="greeting">Hey {display_name},</p>
      <p>{desc}</p>
      
      <div class="terminal-window">
        <div class="terminal-header">
          <span class="terminal-dot dot-red"></span>
          <span class="terminal-dot dot-yellow"></span>
          <span class="terminal-dot dot-green"></span>
          <span class="terminal-title">utim cli — status check</span>
        </div>
        <div class="code-block">
          <div><span class="code-prompt">$</span> <span class="code-cmd">utim</span> /usage</div>
        </div>
      </div>
      
      <div style="margin-top: 28px;">
        <a href="https://utim.dev/pricing" class="btn {btn_class}">{btn_label}</a>
      </div>
    """
    return send_email(to_email, subject, _base_template(body))


def send_bonus_credits_email(to_email: str, display_name: str, bonus_credits: float) -> bool:
    """Send an email informing the user they received bonus credits from degradation."""
    subject = "🎁 Bonus Credits Added to Your UTIM Account"
    bonus_usd = bonus_credits / 1000.0
    body = f"""
      <div class="badge badge-emerald">● BONUS_CREDITS_GRANTED</div>
      <h1 class="email-title">Bonus credits added</h1>
      <p class="greeting">Hey {display_name},</p>
      <p>
        Your account has been credited with bonus tokens following your plan transition.
        These credits are available for immediate use across all terminal sessions.
      </p>
      
      <div class="highlight-box">
        <div class="amount">{bonus_credits:,.0f} Credits <span>&approx; ${bonus_usd:.2f} USD</span></div>
        <p style="margin-top: 10px; margin-bottom: 0; font-size: 13px; color: #71717a;">
          Bonus credits are automatically consumed prior to your monthly allocation.
        </p>
      </div>
      
      <div style="margin-top: 28px;">
        <a href="https://utim.dev/pricing" class="btn btn-primary">View Account Balance &rarr;</a>
      </div>
    """
    return send_email(to_email, subject, _base_template(body))
