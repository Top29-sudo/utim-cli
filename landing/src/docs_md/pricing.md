# UTIM CLI Pricing Plans

UTIM offers several flexible compute node plan tiers tailored to different developer workflows and credit consumption needs.

## Subscription Tiers & Allowance Limits

| Plan Tier | Price (monthly) | Monthly Credit Allowance | Target Audience / Use Cases |
| :--- | :--- | :--- | :--- |
| **Free Plan** | $0.00 / mo | 100 credits / 5 hrs | 100 credits auto-refilled every 5 hours (up to 3,000 monthly credits). |
| **Hobby Plan** | $7.00 / mo | 4,000 credits (+500 1st purchase bonus) | Indie developers exploring coding MoEs and low-cost reasoning tools. |
| **Pro Plan** | $25.00 / mo | 18,000 credits (+2,000 1st purchase bonus) | Professional developers seeking the perfect balance of reasoning power and budget. |
| **Max Plan** | $55.00 / mo | 45,000 credits (+5,000 1st purchase bonus) | Advanced builders running heavy scrollytelling visual agents and complex structures. |
| **Ultimate Plan** | $110.00 / mo | 90,000 credits (+12,000 1st purchase bonus) | Elite power users utilizing ultra-premium heavy models without constraints. |

---

## Plan Upgrades & Payment
* Users can subscribe or upgrade their plan directly from the web client UI (profile page) using our integrated Razorpay payment gateway.
* Credit consumption is calculated dynamically based on input and output tokens consumed. Free models are priced at **$0.02 / 1M in and $0.03 / 1M out** for Free plan users, while all Paid plan users receive a **10x priority discount at $0.002 / 1M in and $0.003 / 1M out**. Standard premium model prices are synced daily with OpenRouter and include a flat 5% platform markup.
* All paid plans allow accessing the full registry of models, though recommended selections exist per plan tier to optimize credit limits.
* Free and paid users can also use the Bring Your Own Key (BYOK) option to connect their own custom provider keys and URLs, bypassing UTIM quota limits entirely.
* **Credit Top-Up Payments & Conversion Rates**: One-time credit top-ups (ranging from $2.00 to $4,500.00) are converted dynamically to Indian Rupees (INR) using real-time market exchange rates plus a platform markup fee (varying from 2% to 5% depending on the amount). Top-up credits are added instantly to your account as bonus quota at `$1.00 USD = 1,000 credits`.

---

## Credit & Quota Recalculation Engine

UTIM CLI uses an automated, server-authoritative credit settlement and quota recalculation engine:

1. **5-Hour Cycle Slot Recalculation**:
   Every 5 hours, the server recalculates active slot capacity (`100 credits` for Free users, or fractional plan quota). Unused slot credits from the preceding cycle automatically roll over into the **Quota Bank** (storing up to 2 months' capacity).

2. **Deduction Priority Cascade**:
   Turn deductions execute in strict priority order:
   - **Priority 1**: `Bonus Quota` (top-up credits & downgrade conversions - consumed first)
   - **Priority 2**: `Five-Hour Slot Quota` (active cycle allocation)
   - **Priority 3**: `Quota Bank` (rollover reserves - consumed when active 5h slot is depleted)

3. **Dynamic Token Pricing & 10x Discount Recalculation**:
   - **Free Models (`:free`)**: Billed at `$0.02 / 1M in` & `$0.03 / 1M out` for Free tier accounts, and automatically recalculated to a **10x priority discount ($0.002 in / $0.003 out per 1M)** for all Paid plan subscribers.
   - **Premium Models**: Billed at `$1.00 USD = 1,000 credits`. Prompt and completion tokens are recalculated per turn plus a 5% platform markup fee.

4. **Downgrade & Tier Change Balance Recalculation**:
   When downgrading or switching plans mid-billing-cycle, remaining credits are recalculated: 50% of the unused balance is converted into non-expiring **Bonus Quota** so earned credits are never lost.

5. **BYOK Zero-Deduction Override (`/byok`)**:
   Configuring custom provider keys routes LLM completion calls directly to your provider, bypassing UTIM credit recalculation entirely.
