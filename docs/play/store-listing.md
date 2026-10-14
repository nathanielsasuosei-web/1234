# Play Store listing

Copy for the Play Console, plus the answers to the forms that trip people up. Graphics
live next to this file: `icon-512.png` (512 × 512) and `feature-graphic-1024x500.png`.

---

## Store listing

**App name** (30 characters max)

```
Meetbeatz — Beats & Studio
```

**Short description** (80 characters max)

```
Buy Afrobeats, amapiano and drill beats. Pay with Mobile Money, get files instantly.
```

**Full description** (4000 characters max)

```
Meetbeatz is the studio store of producer Meetbeatz — Afrobeats, amapiano, ghanapiano
and asakaa instrumentals, priced in Ghana cedis, paid with Mobile Money, delivered to
your inbox the moment you buy.

16 beats in store, and every one is an original work recorded in Accra.

BROWSE AND PREVIEW
Stream a full preview before you spend anything. Filter by genre, BPM, key or mood, or
search for the artist you write like. Each beat shows its tempo, key and the tags the
producer filed it under, so you know what you are getting before you tap play.

FOUR LICENSE TIERS
Basic lease for demos and streaming, premium lease with the WAV, unlimited with the
stems, and exclusive rights that remove the beat from the store for good. Every tier
shows exactly which files and what you may do with them, and the licensing guide is one
tap away.

PAY THE WAY GHANA PAYS
MTN Mobile Money, Telecel Cash, AirtelTigo Money and cards, through Paystack. You
approve the payment on your own phone with your PIN — the app never sees it. Files and
your signed licence arrive by email straight afterwards, and stay in Your Account.

SOUND KITS
Free drum kits, loops and sample packs from the studio. Download them and drop them
straight into your next session.

BOOK STUDIO TIME
Recording, mixing, mastering and online sessions with the producer. Pick a service, a
date and a start time, pay a 50% deposit with Mobile Money to lock the slot, and settle
the balance at the studio.

RECORD ONLINE
No booth? A vocal room in your phone: record a take over any beat with headphone
monitoring and a live level meter, keep the good ones, and send the best to the studio
to book the live session.

FINISH THE RELEASE
Distribution to the streaming services with ISRC and UPC codes assigned for you, and a
colour adjuster that grades cover art to a 3000 × 3000 square the stores accept.

SECURE AND HONEST
Mobile Money and card payments are processed by Paystack, never stored by the app.
Files you paid for download to your phone. No subscription, no hidden fees, and a real
producer on the other end — the studio is in Accra and the WhatsApp number answers.

Meetbeatz. Beats, licenses and studio sessions — from the studio in Accra to your phone.
```

**Category:** Music & Audio
**Tags:** music, beats, audio, producer
**Contact email:** mrmeetbeeatz@gmail.com
**Contact phone:** +233 25 651 4595
**Website:** https://meetbeatz.com
**Privacy policy:** https://meetbeatz.com/privacy

---

## App content

**Ads:** the site shows AdSense slots on public pages. Answer honestly: *yes, the app
contains ads*.

**In-app purchases:** physical/real-world services are sold and delivered (beats, studio
time, distribution). On Play, that is *not* an in-app purchase in the billing sense
because the products are not consumed inside a digital storefront of in-app items —
they are downloads and studio bookings, which is the same category as buying a physical
product. Do not claim "no purchases"; describe them in the store listing text, which the
listing above does.

**Target audience:** 13+ (the store sells licences to working artists and producers).
Answer the content questionnaire as *not designed for children*.

**Content rating questionnaire:** Music/entertainment app. No violence, no sexual
content, no gambling, no user-to-user content shown publicly. One honest flag: the
storefront contains song titles and tags that reference artist names; none of them are
explicit. Expect an *Everyone* or *Teen* rating.

**Government apps:** no. **Financial features:** no — payments are processed by a
third-party provider (Paystack), and the app never holds funds or extends credit.

---

## Data safety

The app is a Trusted Web Activity: the Android app itself collects nothing. The website
inside it collects the data below, and Play's form is about what the *app* does, so the
defensible answers are:

| Question | Answer |
| --- | --- |
| Does your app collect or share any of the required user data types? | **Yes** — via the website it hosts. |
| Data types | **Personal info:** name, email, phone number (account, orders). **Financial info:** purchase history (orders, licences). **App activity:** in-app search history and page views, for the storefront and its analytics. |
| Is this data collected, shared, or both? | Collected. Shared with payment processors (Paystack) and hosting/mail infrastructure, not sold. |
| Is the data encrypted in transit? | **Yes** — HTTPS only; the app refuses to downgrade to HTTP and cancels on a certificate error. |
| Can users request deletion? | **Yes** — via `/contact`, or by email to the address above. |
| Is data collected for advertising? | AdSense slots are present on public pages; declare if the account is configured for personalised ads. |

The microphone is requested for the online recording booth, and camera for video takes.
Both are optional: the app installs and works without granting either.

---

## Screenshots

Play needs at least 2 phone screenshots; 4–8 is normal. Take them on a device with the
app installed (Power + Volume Down), then trim the status bar if you want them tidy:

1. The home page — the artist photo, "Fresh from the lab", the marquee.
2. The beat store grid with covers visible.
3. A beat page with the licence tiers and the "from GHS 200.00" price.
4. The studio booking page with the calendar.
5. Mobile Money as the selected payment method.
6. The recording booth with a take recorded.

Add captions on the images themselves ("Preview every beat before you pay", "Pay with
MTN Mobile Money"), because Play shows them small.

---

## Uploading

The upload is automated — **Actions → Publish to Google Play → Run workflow**. It builds
a signed bundle, uploads it to the track you pick, attaches the R8 mapping for readable
crash reports, and on the default `internalsharing` track prints a URL that installs the
app on your phone in minutes with no review. GitHub only offers that button once the
workflow is on `main`, so before the merge, tag the commit instead — `git tag v1.0.0 &&
git push origin v1.0.0` triggers the identical job. The one-time setup (upload key, app
entry, service account) is in [§5 of the app docs](../ANDROID_APP.md#5-publishing-to-google-play).

Release notes for that upload live in [`release-notes/`](release-notes/) —
`whatsnew-en-US.txt` is what testers and customers read under "What's new", so edit it
before each release.

## Release checklist

- [ ] `assetlinks.json` deployed with the **Play App Signing** fingerprint (§3 of
      `docs/ANDROID_APP.md`) — Play rejects a TWA whose domain is not verified.
- [ ] `versionCode` bumped (`tools/bump_version_code.sh --name x.y.z`).
- [ ] Signed AAB uploaded — run **Publish to Google Play** with track `internalsharing`
      first to install it from Play on your own phone, then `production`.
- [ ] Store listing text, icon and feature graphic uploaded from this folder.
- [ ] Data safety, content rating and app-access forms completed.
- [ ] Internal testing release installed on your own phone and checked end to end: browse
      → preview → add to cart → checkout → download the file.
- [ ] Closed testing track running for the required period before production.
