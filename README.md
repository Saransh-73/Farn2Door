# Farm2Door — Connected Static Prototype

All 10 pages are now wired together into one clickable site. Open
`index.html` in a browser (or serve the folder with any static server)
and click through — every button/link that had `href="#"` now points
somewhere real, and the JS "submit"/"continue" handlers redirect to
the next real page instead of just showing a toast.

## Files → route (maps to `farm2door-structure.md`)

| File                      | Acts as (Next.js route)                          |
|---------------------------|---------------------------------------------------|
| `index.html`              | `app/page.tsx` (public landing)                    |
| `login.html`              | `(auth)/login/page.tsx` — role tabs: farmer/consumer/bulk/delivery/admin |
| `signin.html`             | `(auth)/otp/page.tsx` — phone + OTP flow (consumer sign-up path) |
| `marketplace.html`        | `(buyer)/marketplace/page.tsx`                     |
| `checkout.html`           | `(buyer)/checkout/page.tsx`                        |
| `farmer-dashboard.html`   | `(farmer)/dashboard/page.tsx`                      |
| `delivery-dashboard.html` | `(delivery)/dashboard/page.tsx`                    |
| `admin-dashboard.html`    | `(admin)/dashboard/page.tsx`                       |
| `traceability.html`       | `traceability/[qrCode]/page.tsx`                   |
| `notifications.html`      | `notifications/page.tsx`                           |

## How the flows connect

- **Landing → Login**: the "Log in as" dropdown and the 5 role cards
  each link to `login.html?role=<role>`. `login.html` reads that
  query param on load and preselects the matching role tab.
- **Login → Dashboard**: submitting the (client-validated) login form
  redirects to the right dashboard per role: `farmer-dashboard.html`,
  `marketplace.html` (consumer), `marketplace.html?mode=bulk` (bulk
  buyer), `delivery-dashboard.html`, or `admin-dashboard.html`.
- **Login ⇄ Sign-in**: the "Sign in with OTP instead" button on
  `login.html` goes to `signin.html`; "Create an account" does too.
  Completing the OTP flow on `signin.html` redirects to
  `marketplace.html`.
- **Marketplace → Checkout → Confirmation**: "Proceed to checkout"
  in the cart drawer now navigates to `checkout.html`. After an order
  is placed, "Track order" opens `traceability.html?qr=<orderId>` and
  "View cart again" returns to `marketplace.html`.
- **Dashboards → Notifications**: the bell icon on marketplace,
  farmer, delivery, and admin dashboards all open
  `notifications.html`.
- **Delivery dashboard → Traceability**: opening a delivery's detail
  modal now has a "View trace" button that opens
  `traceability.html?qr=<order>`.
- **Traceability deep-link**: `traceability.html` now reads `?qr=`
  from the URL. It matches one of the 4 built-in sample batches
  (tomato/rice/turmeric/mango) if the ID matches; otherwise it shows
  a sample trace with a toast noting there's no exact record yet —
  since order IDs from checkout/delivery are randomly generated and
  won't match the 4 hardcoded demo batches. Wire this to a real API
  lookup once the backend exists.
- **Admin dashboard**: sidebar items now scroll to the matching
  section on the page (`#orders`, `#farmers`, `#verification`,
  `#logistics`). "Payments" and "Settings" are left as `#` since no
  content for them exists yet in this prototype.
- Every page's logo/brand now links back to `index.html`.

## Honest gaps (left as `href="#"` on purpose)

These don't have a corresponding page in what you uploaded, so I
left them unlinked rather than fake a destination:
- Footer "About us / Careers / Contact" on the landing page
- "Need help?" / "Forgot password?" on the auth pages
- "Help centre" on marketplace/traceability
- "View all notifications" (the page already shows everything)
- Admin "Payments" and "Settings" sidebar items

## Next step toward the real Next.js app

This is still plain HTML/CSS/JS — it's meant to prove out the flow
and screen designs. To turn it into the actual app in
`farm2door-structure.md`, each file's `<style>` block becomes Tailwind
classes, each inline `<script>` becomes a client component using
`useState`/`useCart`/`useAuth`, and the hardcoded arrays (`PRODUCTS`,
`deliveries`, `notifications`, etc.) get replaced with calls to
`lib/api.ts` hitting the FastAPI backend.
