# Service Level Agreement (SLA)

*Effective: July 2026*

This SLA defines the service commitments for UTIM users.

---

## 1. Service Availability

| Plan Tier | Uptime Target | Downtime Allowance (monthly) |
|-----------|---------------|------------------------------|
| Free      | 99.0%         | ~7.3 hours                   |
| Hobby     | 99.5%         | ~3.6 hours                   |
| Pro       | 99.9%         | ~43 minutes                  |
| Team      | 99.9%         | ~43 minutes                  |
| Enterprise| 99.99%        | ~4.3 minutes                 |

> **Note**: Scheduled maintenance is excluded from downtime calculations. We provide 24-hour advance notice for planned maintenance.

---

## 2. Support Response Times

| Plan Tier | Critical (API down) | High (Major feature broken) | Medium (Minor issue) | Low (General inquiry) |
|-----------|---------------------|----------------------------|----------------------|----------------------|
| Free      | 48 hours           | 72 hours                  | 5 business days     | 10 business days    |
| Hobby     | 24 hours           | 48 hours                  | 3 business days     | 7 business days     |
| Pro       | 8 hours            | 24 hours                  | 2 business days     | 5 business days     |
| Team      | 4 hours            | 12 hours                  | 1 business day      | 3 business days     |
| Enterprise| 1 hour             | 4 hours                   | 24 hours            | 2 business days     |

---

## 3. Issue Severity Definitions

| Severity | Description | Examples |
|----------|-------------|----------|
| **Critical** | Complete service outage, data loss risk | API completely unreachable, cannot login, payment processing broken |
| **High** | Major feature unavailable | Chat completion fails, quota system broken, cannot upgrade plan |
| **Medium** | Feature partially works | Slow responses, occasional errors, UI glitches |
| **Low** | Cosmetic or enhancement | Typos, documentation requests, feature suggestions |

---

## 4. Maintenance Windows

- **Scheduled Maintenance**: Announced 24+ hours in advance via Discord and status page
- **Emergency Maintenance**: May occur without notice for critical security patches; we aim to minimize disruption
- **Region Maintenance**: Cloud infrastructure updates may affect specific regions

---

## 5. Credit/Quota System

- **Refill Timeliness**: Automatic quota refills process within 5 minutes of the scheduled time
- **Billing Accuracy**: Credits are calculated based on actual token usage; disputes handled within 3 business days
- **Refund Policy**: Unused credits are non-refundable per the Refund Policy

---

## 6. Exclusions

This SLA does NOT cover:

1. **Third-party service failures** (OpenRouter, Anthropic, OpenAI, Google AI)
2. **User-caused issues** (invalid API keys, network restrictions, local configuration errors)
3. **Force majeure** (natural disasters, major internet outages)
4. **Client-side problems** (local CLI installation issues, terminal compatibility)

---

## 7. SLA Credits

For paid plans (Hobby and above), if we fail to meet uptime targets:

| Uptime Miss | Service Credit |
|-------------|----------------|
| 99.0% - 99.5% | 10% of monthly subscription |
| 98.0% - 99.0% | 25% of monthly subscription |
| < 98.0% | 50% of monthly subscription |

> Credits are applied to the next billing cycle. To request credits, contact support with your account details.

---

## 8. Contact

- **Status Page**: status.utim.dev
- **Support Email**: support@utim.dev
- **Discord**: discord.com/invite/wGB7M8pMEy