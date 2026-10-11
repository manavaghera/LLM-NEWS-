import { BookCheck, Cookie, Copyright, Info, Lock, Scale } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { useSiteConfig } from '@/api/queries'

const OUTLETS = 'BBC News, The Guardian, NPR, Al Jazeera, CBC News, Ars Technica and The Verge'

function InfoPage({ icon, kicker, title, intro, children }: {
  icon: ReactNode; kicker: string; title: string; intro: string; children: ReactNode
}) {
  return (
    <div className="mx-auto max-w-3xl">
      <title>{`${kicker} · NewsSense`}</title>
      <meta name="description" content={intro} />
      <link rel="canonical" href={`${window.location.origin}${window.location.pathname}`} />
      <header className="mb-10 space-y-3 border-b border-rule pb-8">
        <p className="flex items-center gap-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">{icon} {kicker}</p>
        <h1 className="headline text-4xl font-semibold tracking-tight sm:text-5xl">{title}</h1>
        <p className="text-lg leading-relaxed text-muted">{intro}</p>
      </header>
      <div className="space-y-10">{children}</div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3 leading-relaxed">
      <h2 className="headline text-2xl font-medium">{title}</h2>
      {children}
    </section>
  )
}

/** The contact email from the server's CONTACT_EMAIL, or the article button when none is set */
function Contact({ purpose }: { purpose: string }) {
  const config = useSiteConfig().data
  const email = config?.contact_email
  return <div className="space-y-2">{email ? (
    <p>
      For {purpose}, email <a href={`mailto:${email}`} className="font-medium text-accent hover:underline">{email}</a>.
    </p>
  ) : (
    <p>For {purpose}, use the “Report a problem” button at the end of any article.</p>
  )}{config?.contact_address && <address className="whitespace-pre-line not-italic text-muted">{config.contact_address}</address>}</div>
}

export function AboutPage() {
  return (
    <InfoPage icon={<Info className="size-4" aria-hidden />} kicker="About" title="How NewsSense works"
      intro="NewsSense summarises the news with AI and shows its working: every section links to the reporting it is based on, and a second AI checks each statement before a story is published.">
      <Section title="Where the news comes from">
        <p>
          Stories come from the public news feeds of {OUTLETS}. Where a publisher allows it, the AI reads the full
          article; publishers that ask AI services not to use their articles are summarised from their headline and
          summary only. NewsSense is not affiliated with any of these outlets: the reporting and photos are theirs, and
          each article credits and links to them.
        </p>
      </Section>
      <Section title="How a story is written">
        <p>
          Reports of the same event from different outlets are grouped into one story. An AI model writes a short
          article in its own words, and each section cites its sources with numbered links. Every article names the
          model that wrote it. The front page is refreshed through the day and shows when the next update is due;
          stories added since the morning are marked <strong>New</strong>.
        </p>
      </Section>
      <Section title="How it is fact-checked">
        <p>
          A second AI pass, named on each article, compares every statement with the sources and removes the ones
          they don't support. Each article says how many statements were removed and lets you read them, and{' '}
          <Link to="/trends" className="text-accent hover:underline">Trends</Link> tracks these results over time. If
          the check can't run, the story isn't published. When several outlets cover a story, the article also compares
          how each of them framed it.
        </p>
      </Section>
      <Section title="What to keep in mind">
        <p>
          AI makes mistakes, and an AI fact-check is not a human editor. For anything important, follow the source links
          and read the original reporting. Chat answers, translations, the daily digest and audio are machine-generated
          from the same stories.
        </p>
      </Section>
      <Section title="Corrections">
        <p>If something is wrong or missing, tell us: reports are kept for review and counted on Trends. Published corrections appear with a date on the article, so you can see what was clarified.</p>
        <Contact purpose="corrections" />
        <p><Link to="/privacy" className="text-accent hover:underline">How we handle your data →</Link></p>
      </Section>
    </InfoPage>
  )
}

export function PrivacyPage() {
  return (
    <InfoPage icon={<Lock className="size-4" aria-hidden />} kicker="Privacy" title="Your privacy"
      intro="The short version: no reader accounts, no ads and no tracking cookies. We keep aggregate usage counters without visitor profiles.">
      <Section title="Stored in your browser only">
        <p>
          Saved stories, followed stories and topics, story alerts and your light or dark choice are kept in your browser’s local storage.
          Clearing this site’s data removes them. Library export and import lets you move your saved stories and follows between browsers yourself.
          While this site is open, your browser checks the latest edition for topic matches and requests updates to the individual stories you follow. These requests reveal which article pages are being checked; the server does not store your follows as an account or profile.
        </p>
      </Section>
      <Section title="What our server sees">
        <p>
          Like any website, our server receives your IP address, the page you ask for and your browser type. We use them
          to deliver pages, keep the service secure, and limit how many AI requests one visitor can make: those counts
          are kept in memory for at most a day. Server logs are kept briefly and overwritten automatically.
        </p>
      </Section>
      <Section title="Privacy-safe analytics">
        <p>We count broad actions such as page views, searches, saves and model comparisons, plus route speed and error totals. These counters contain no IP address, cookie identifier, search text, story identifier or user profile. They help us improve the site and spot failures.</p>
      </Section>
      <Section title="Chat questions">
        <p>
          A question you ask is sent, with the day’s stories, to the AI provider this site uses so it can answer. We
          don’t store your questions; the provider processes them under its own terms. Please don’t include personal
          information in them.
        </p>
      </Section>
      <Section title="Problem reports">
        <p>
          A report stores the article, the kind of problem, your message and the time. It does not store your IP address
          or anything else that identifies you, so please leave personal details out of the message.
        </p>
      </Section>
      <Section title="Other services">
        <p>
          The site loads no third-party scripts, fonts or trackers. Our server, not your browser, talks to the news
          feeds, the AI provider and the text-to-speech service. They receive article text and the chat questions you
          type, never anything else about you.
        </p>
      </Section>
      <Section title="Questions">
        <Contact purpose="privacy questions" />
        <p className="text-sm text-muted">Last updated 11 October 2026.</p>
      </Section>
    </InfoPage>
  )
}

export function TermsPage() {
  return <InfoPage icon={<Scale className="size-4" />} kicker="Terms" title="Terms of use" intro="NewsSense is an experimental news and model-research service. Use it as a starting point and verify important decisions with the linked primary sources.">
    <Section title="Using the service"><p>You may read, link to and share NewsSense pages for lawful personal or business use. Do not attempt to bypass access controls, overload the service, scrape it in a way that harms availability, or present generated summaries as original publisher reporting.</p></Section>
    <Section title="Accuracy and availability"><p>AI-generated summaries, translations, audio, comparisons and chat answers can be incomplete or wrong. The service may change or be unavailable. Nothing here is legal, medical, financial or investment advice.</p></Section>
    <Section title="Your responsibility"><p>Check original reporting and official model documentation before relying on a claim, price or specification. You are responsible for decisions made from the service.</p></Section>
    <Section title="Contact"><Contact purpose="terms questions" /><p className="text-sm text-muted">Effective 11 October 2026.</p></Section>
  </InfoPage>
}

export function CookiePolicyPage() {
  return <InfoPage icon={<Cookie className="size-4" />} kicker="Cookies" title="Cookie policy" intro="NewsSense uses one necessary admin-session cookie. Reader preferences are stored locally in the browser and are not tracking cookies.">
    <Section title="Admin session"><p>After a successful owner login, the server sets a secure, HTTP-only, same-site session cookie. It expires after eight hours and is used only to protect administration controls.</p></Section>
    <Section title="Reader settings"><p>Theme, onboarding status, saved stories, followed topics, alerts and model notes use local storage. They stay on your device and can be removed by clearing this site’s data.</p></Section>
    <Section title="Third parties"><p>The site does not load advertising, analytics or social-media cookies.</p></Section>
  </InfoPage>
}

export function SourcesPolicyPage() {
  return <InfoPage icon={<Copyright className="size-4" />} kicker="Sources & copyright" title="How we use reporting" intro="Publishers own their reporting, images and trademarks. NewsSense links to sources and creates short, attributed summaries in its own words.">
    <Section title="Source policy"><p>Each published report identifies its source outlets and provides direct links. Claim evidence shows short supporting excerpts where available. Robots directives and source access limits are respected.</p></Section>
    <Section title="Copyright"><p>NewsSense does not claim ownership of publisher material. Images retain their source credit. Rights holders can request correction, attribution changes or removal.</p></Section>
    <Section title="Requests"><Contact purpose="copyright, attribution or removal requests" /></Section>
  </InfoPage>
}

export function CorrectionsPolicyPage() {
  return <InfoPage icon={<BookCheck className="size-4" />} kicker="Corrections" title="Corrections policy" intro="Readers can report problems on every article. We keep a review record and display published corrections beside the report.">
    <Section title="Review process"><p>Reports are placed in the owner review queue. The editor checks the cited sources and claim evidence, then resolves, dismisses or publishes a correction. A correction includes its publication date and remains attached to the article.</p></Section>
    <Section title="Publication safeguards"><p>Stories are held back when verification fails, when a headline is unsupported, or when the checking response is malformed. Held stories remain visible to the owner and are not silently published.</p></Section>
    <Section title="Report a concern"><Contact purpose="corrections" /></Section>
  </InfoPage>
}
