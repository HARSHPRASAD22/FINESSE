import { useRef } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'
import {
  ArrowDown,
  ArrowRight,
  Bot,
  Building2,
  Check,
  FileCheck2,
  Globe2,
  Map,
  Search,
  ShieldCheck,
} from 'lucide-react'
import './LandingPage.css'
import permitpilotLogo from './assets/permitpilot-logo.png'
import LanguageVoiceControls from './components/LanguageVoiceControls'
import { translate, type Locale } from './lib/i18n'

type LandingDestination = 'overview' | 'agent' | 'onboarding' | 'membership'

const approachCards = [
  {
    number: '01 / DESCRIBE',
    title: 'Start with your goal',
    description: 'Explain what you want to do in everyday language. You do not need to know the permit name first.',
    icon: Bot,
    destination: 'agent' as const,
  },
  {
    number: '02 / CONFIRM',
    title: 'Make your facts yours',
    description: 'Review suggested business details and confirm them before they inform a compliance assessment.',
    icon: Building2,
    destination: 'onboarding' as const,
  },
  {
    number: '03 / TRACE',
    title: 'See the source',
    description: 'Inspect captured public-page excerpts and links. Source coverage is limited and findings need verification.',
    icon: Search,
    destination: 'agent' as const,
  },
  {
    number: '04 / REVIEW',
    title: 'Keep people in control',
    description: 'Review known facts, open questions, and research leads before taking the next step yourself.',
    icon: FileCheck2,
    destination: 'agent' as const,
  },
]

function LandingPage({ onOpenWorkspace, locale, onLocaleChange }: {
  onOpenWorkspace: (destination: LandingDestination) => void
  locale: Locale
  onLocaleChange: (locale: Locale) => void
}) {
  const pointerRef = useRef<HTMLDivElement>(null)
  const boardRef = useRef<HTMLDivElement>(null)

  const handlePointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    if (event.pointerType !== 'mouse' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    if (pointerRef.current) {
      pointerRef.current.style.left = `${event.clientX}px`
      pointerRef.current.style.top = `${event.clientY}px`
      pointerRef.current.style.opacity = '1'
    }

    const board = boardRef.current
    if (!board) return
    const bounds = board.getBoundingClientRect()
    const x = (event.clientX - bounds.left) / bounds.width - 0.5
    const y = (event.clientY - bounds.top) / bounds.height - 0.5
    if (Math.abs(x) < 1.1 && Math.abs(y) < 1.1) {
      board.style.transform = `perspective(1100px) rotateY(${x * 5}deg) rotateX(${-y * 5}deg) translateY(-2px)`
    }
  }

  const resetPointer = () => {
    if (pointerRef.current) pointerRef.current.style.opacity = '0'
    if (boardRef.current) boardRef.current.style.transform = ''
  }

  return (
    <div className="public-landing" onPointerMove={handlePointerMove} onPointerLeave={resetPointer}>
      <div className="public-landing__noise" aria-hidden="true" />
      <div className="public-landing__pointer" ref={pointerRef} aria-hidden="true" />
      <div className="public-landing__announcement">
        {translate('A clearer route through complex approvals', locale)} <span>✳</span> {translate('Built around your next step', locale)}
      </div>
      <header className="public-landing__nav">
        <a href="#landing-top" className="public-landing__brand" aria-label={translate('PermitPilot home', locale)}>
          <img className="public-landing__brand-logo" src={permitpilotLogo} alt="" />
          <small>BETA</small>
        </a>
        <nav className="public-landing__nav-links" aria-label={translate('Landing page sections', locale)}>
          <a href="#approach">{translate('The approach', locale)}</a>
          <a href="#journey">{translate('How it works', locale)}</a>
          <a href="#intelligence">{translate('What makes it different', locale)}</a>
        </nav>
        <div className="public-landing__nav-actions">
          <LanguageVoiceControls locale={locale} onLocaleChange={onLocaleChange} targetSelector=".public-landing main" />
          <button className="public-landing__text-link" onClick={() => onOpenWorkspace('membership')}>{translate('Membership', locale)}</button>
          <button className="public-landing__button public-landing__button--small" onClick={() => onOpenWorkspace('overview')}>
            {translate('Open workspace', locale)} <ArrowRight size={14} />
          </button>
        </div>
      </header>
      <div className="public-landing__ticker" aria-label={locale === 'hi' ? 'PermitPilot प्रक्रिया' : 'PermitPilot journey'}>
        <div className="public-landing__ticker-track">
          {Array.from({ length: 2 }, (_, index) => (
            <span className="public-landing__ticker-group" key={index}>
              <span>{locale === 'hi' ? '01 / बताएँ' : '01 / DESCRIBE'}</span><i>✳</i><span>{locale === 'hi' ? '02 / पुष्टि' : '02 / CONFIRM'}</span><i>✳</i><span>{locale === 'hi' ? '03 / शोध' : '03 / RESEARCH'}</span><i>✳</i><span>{locale === 'hi' ? '04 / समीक्षा' : '04 / REVIEW'}</span><i>✳</i><span>{locale === 'hi' ? '05 / आगे बढ़ें' : '05 / MOVE FORWARD'}</span><i>✳</i>
            </span>
          ))}
        </div>
      </div>

      <main id="landing-top">
        <section className="public-landing__hero">
          <div className="public-landing__hero-grid">
            <div className="public-landing__hero-copy">
              <div className="public-landing__eyebrow">{translate('A better way through the paperwork', locale)}</div>
              <h1>{translate('Big plans.', locale)}<br /><em>{translate('Clear next steps.', locale)}</em></h1>
              <p>{translate('Permits should not feel like a maze. Start with what you want to do, review candidate requirements, and see the public-source evidence behind your next steps.', locale)}</p>
              <div className="public-landing__hero-actions">
                <button className="public-landing__button" onClick={() => onOpenWorkspace('agent')}>{translate('Map my permit journey', locale)} <ArrowRight className="public-landing__arrow" size={16} /></button>
                <a className="public-landing__button public-landing__button--outline" href="#approach">{translate('Explore the approach', locale)} <ArrowDown size={15} /></a>
              </div>
              <div className="public-landing__proof">
                <span className="public-landing__proof-icons"><i><Check size={12} /></i><i><Search size={12} /></i><i><ShieldCheck size={12} /></i></span>
                <span><b>{translate('Clarity at every checkpoint.', locale)}</b> {translate('Guidance, evidence, and progress in one place.', locale)}</span>
              </div>
            </div>
            <div className="public-landing__hero-art">
              <div className="public-landing__float-card public-landing__float-card--one">
                <span>{translate('YOUR ROUTE, MAPPED', locale)}</span><strong><i><Check size={11} /></i> {translate('Candidate checks identified', locale)}</strong>
                <div className="public-landing__mini-progress"><i /></div>
              </div>
              <div className="public-landing__route-board" ref={boardRef}>
                <div className="public-landing__board-top"><span>PP / {translate('ROUTE MAP', locale)} 001</span><span className="public-landing__live">{translate('GUIDED PATHWAY', locale)}</span></div>
                <div className="public-landing__board-title"><small>{translate('FROM IDEA TO PREPARATION', locale)}</small><h2>{translate('A route that makes sense.', locale)}</h2></div>
                <svg className="public-landing__route-svg" viewBox="0 0 590 390" role="img" aria-label={locale === 'hi' ? 'लक्ष्य से समीक्षा तक PermitPilot प्रक्रिया का चित्र' : 'Illustration of the PermitPilot journey from goal to review'}>
                  <path className="public-landing__route-glow" d="M75 105 C145 105 145 210 220 210 S315 115 375 157 S440 260 510 265" />
                  <path className="public-landing__route-line" d="M75 105 C145 105 145 210 220 210 S315 115 375 157 S440 260 510 265" />
                  <g className="public-landing__route-node" transform="translate(75 105)"><circle className="outer" r="20" /><circle className="inner" r="6" /><text x="-2" y="-34">01 / {locale === 'hi' ? 'लक्ष्य' : 'GOAL'}</text><text className="sub" x="-2" y="38">{translate('Describe your plan', locale)}</text></g>
                  <g className="public-landing__route-node" transform="translate(220 210)"><circle className="outer" r="20" /><circle className="inner" r="6" /><text x="-2" y="-34">02 / {locale === 'hi' ? 'तथ्य' : 'FACTS'}</text><text className="sub" x="-2" y="38">{translate('Confirm what is known', locale)}</text></g>
                  <g className="public-landing__route-node" transform="translate(375 157)"><circle className="outer" r="20" /><circle className="inner" r="6" /><text x="-2" y="-34">03 / {locale === 'hi' ? 'स्रोत' : 'SOURCES'}</text><text className="sub" x="-2" y="38">{translate('Inspect public evidence', locale)}</text></g>
                  <g className="public-landing__route-node" transform="translate(510 265)"><circle className="outer" r="20" /><circle className="inner" r="6" /><text x="-2" y="-35" textAnchor="end">04 / {locale === 'hi' ? 'समीक्षा' : 'REVIEW'}</text><text className="sub" x="-2" y="38" textAnchor="end">{translate('You decide what is next', locale)}</text></g>
                </svg>
                <div className="public-landing__board-bottom"><span>{locale === 'hi' ? 'मानव-निर्देशित · स्रोत-संबद्ध' : 'HUMAN-LED · SOURCE-LINKED'}</span><b>{locale === 'hi' ? 'तैयारी / आवेदन जमा नहीं' : 'PREPARATION / NOT SUBMISSION'}</b></div>
              </div>
              <div className="public-landing__float-card public-landing__float-card--two">
                <span>{locale === 'hi' ? 'शोध की झलक' : 'RESEARCH SNAPSHOT'}</span><strong>{locale === 'hi' ? 'सार्वजनिक पेज के अंश' : 'Public page excerpts'}</strong>
                <div className="public-landing__sparkline"><i /><i /><i /><i /><i /><i /><i /></div>
              </div>
              <div className="public-landing__seal"><Globe2 size={26} /><span>{locale === 'hi' ? <>सार्वजनिक स्रोत<br />मानवीय समीक्षा</> : <>PUBLIC SOURCES<br />HUMAN REVIEW</>}</span></div>
            </div>
          </div>
        </section>

        <section className="public-landing__section public-landing__section--dark" id="approach">
          <div className="public-landing__inner">
            <div className="public-landing__section-head">
              <div><div className="public-landing__eyebrow">{locale === 'hi' ? 'कम अनुमान, अधिक संदर्भ' : 'Less guesswork, more context'}</div><h2>{translate('One goal.', locale)}<br /><em>{translate('A clearer route.', locale)}</em></h2></div>
              <p>{locale === 'hi' ? 'PermitPilot व्यवसाय की जानकारी, संभावित अनुपालन जाँच और स्रोत शोध को एक जगह लाता है—और अनिश्चित विवरणों को आपकी पुष्टि के लिए स्पष्ट रखता है।' : 'PermitPilot brings business facts, candidate compliance checks, and source research together—while keeping uncertain details visible for you to verify.'}</p>
            </div>
            <div className="public-landing__feature-grid">
              {approachCards.map(({ number, title, description, icon: Icon, destination }) => (
                <button className="public-landing__feature-card" key={number} onClick={() => onOpenWorkspace(destination)}>
                  <span className="public-landing__feature-number">{translate(number, locale)}</span>
                  <span className="public-landing__feature-icon"><Icon size={21} /></span>
                  <strong>{translate(title, locale)}</strong>
                  <span className="public-landing__feature-description">{translate(description, locale)}</span>
                  <span className="public-landing__card-arrow"><ArrowRight size={17} /></span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="public-landing__section public-landing__section--process" id="journey">
          <div className="public-landing__inner public-landing__process-layout">
            <div className="public-landing__process-intro">
              <div className="public-landing__eyebrow">{locale === 'hi' ? 'एक बेहतर प्रक्रिया' : 'A more thoughtful journey'}</div>
              <h2>{translate('Less chasing.', locale)}<br /><em>{translate('More knowing.', locale)}</em></h2>
              <p>{locale === 'hi' ? 'सरल भाषा में शुरू करें। बेहतर निर्णय के लिए हर कदम का संदर्भ और सीमाएँ देखें।' : 'Start in plain language. Review each step with the context and caveats you need to make informed decisions.'}</p>
              <button className="public-landing__button" onClick={() => onOpenWorkspace('agent')}>{translate('Start with your goal', locale)} <ArrowRight size={15} /></button>
            </div>
            <div className="public-landing__process-list">
              <article><span className="public-landing__process-icon"><Search size={21} /></span><div><h3>{translate('Describe what you want to do', locale)}</h3><p>{locale === 'hi' ? 'सहायक को अपना लक्ष्य बताएँ। वह अनुमान लगाने के बजाय छूटी हुई जानकारी पूछ सकता है।' : 'Tell the Red Tape Agent your goal. It can ask for specific missing details rather than assuming them.'}</p><small>01 / {translate('GOAL & INTERVIEW', locale)}</small></div></article>
              <article><span className="public-landing__process-icon"><Map size={21} /></span><div><h3>{translate('Review candidate requirements', locale)}</h3><p>{locale === 'hi' ? 'पुष्टि किए गए व्यवसाय विवरणों पर आधारित जाँचें देखें। अस्पष्ट परिणामों की पुष्टि करें।' : 'See checks based on your confirmed business facts. Treat unclear or conditional results as items to verify.'}</p><small>02 / {translate('FACTS & ASSESSMENT', locale)}</small></div></article>
              <article><span className="public-landing__process-icon"><Globe2 size={21} /></span><div><h3>{translate('Inspect available source pages', locale)}</h3><p>{locale === 'hi' ? 'जहाँ उपलब्ध हों, चुने हुए सार्वजनिक पेजों के अंश और स्रोत लिंक देखें।' : 'See excerpts and source links from a bounded read of selected public pages, where the pages can be reached.'}</p><small>03 / {translate('SOURCE RESEARCH', locale)}</small></div></article>
              <article><span className="public-landing__process-icon"><FileCheck2 size={21} /></span><div><h3>{translate('Review before taking action', locale)}</h3><p>{locale === 'hi' ? 'तैयारी-पत्र में ज्ञात जानकारी, कमियाँ और शोध संकेत देखें। आधिकारिक पुष्टि और आवेदन जमा करने की ज़िम्मेदारी आपकी है।' : 'Review known facts, missing details, and research leads in a preparation sheet. You remain responsible for official verification and submission.'}</p><small>04 / {translate('HUMAN CHECKPOINT', locale)}</small></div></article>
            </div>
          </div>
        </section>

        <section className="public-landing__section public-landing__section--intelligence" id="intelligence">
          <div className="public-landing__inner">
            <div className="public-landing__section-head">
              <div><div className="public-landing__eyebrow">{locale === 'hi' ? 'सोच-समझकर बनाया गया' : 'A little more thoughtful by design'}</div><h2>{translate('Useful intelligence.', locale)}<br /><em>{translate('Visible by design.', locale)}</em></h2></div>
              <p>{locale === 'hi' ? 'AI को अनिश्चितता नहीं बढ़ानी चाहिए। यह इंटरफ़ेस स्रोतों, मान्यताओं और सीमाओं को स्पष्ट दिखाता है।' : 'AI should not add another layer of uncertainty. The interface makes its sources, assumptions, and limitations easier to see.'}</p>
            </div>
            <div className="public-landing__intelligence-grid">
              <article className="public-landing__intelligence-card public-landing__intelligence-card--feature">
                <span>01 / {translate('BOUNDED RESEARCH', locale)}</span><h3>{translate('Source links beside the findings.', locale)}</h3>
                <p>{locale === 'hi' ? 'चुने हुए पेजों के अंश समीक्षा के लिए दिखाए जा सकते हैं। यह पूर्ण वेब क्रॉलर नहीं है और हर वर्तमान नियम मिलने की गारंटी नहीं देता।' : 'Selected pages can be captured and excerpts shown for review. This is not a full web crawler or a guarantee that every current rule was found.'}</p>
                <div className="public-landing__source-art"><div><Globe2 size={16} /><span>{locale === 'hi' ? 'सार्वजनिक पेज / स्रोत संकेत' : 'PUBLIC PAGE / SOURCE LEAD'}</span></div><i /><i /><i /><b>{locale === 'hi' ? 'स्रोत खोलें ↗' : 'OPEN SOURCE ↗'}</b></div>
              </article>
              <article className="public-landing__intelligence-card">
                <span>02 / {translate('FACTS YOU CONTROL', locale)}</span><h3>{translate('Confirm before assessing.', locale)}</h3>
                <p>{locale === 'hi' ? 'व्यवसाय विवरण आपकी समीक्षा के लिए हैं। अज्ञात या अपुष्ट जानकारी को निश्चित आवश्यकता न मानें।' : 'Business details are reviewed with you. Unknown or unconfirmed facts should not be mistaken for established requirements.'}</p>
                <div className="public-landing__fact-art"><div><Building2 size={18} /><span>{locale === 'hi' ? 'व्यवसाय प्रोफ़ाइल' : 'BUSINESS PROFILE'}</span></div><p>{locale === 'hi' ? 'गतिविधि' : 'Activity'} <b>{locale === 'hi' ? 'पुष्टि आवश्यक' : 'Needs confirmation'}</b></p><p>{locale === 'hi' ? 'स्थान' : 'Location'} <b>{translate('West Bengal', locale)}</b></p><p>{locale === 'hi' ? 'स्रोत' : 'Source'} <b>{locale === 'hi' ? 'दिख रहा है' : 'Visible'}</b></p></div>
              </article>
              <article className="public-landing__intelligence-card">
                <span>03 / {translate('HUMAN CHECKPOINT', locale)}</span><h3>{translate('Review is not submission.', locale)}</h3>
                <p>{locale === 'hi' ? 'समीक्षा-पत्र ज्ञात जानकारी और कमियाँ व्यवस्थित करता है। यह आधिकारिक फ़ॉर्म, हस्ताक्षर, स्वीकृति या सरकारी आवेदन नहीं है।' : 'The review sheet helps organize known facts and gaps. It is not an official form, signature, approval, or government submission.'}</p>
                <div className="public-landing__review-art"><div><ShieldCheck size={20} /><strong>{locale === 'hi' ? 'पहले समीक्षा' : 'REVIEW FIRST'}</strong></div><span>{locale === 'hi' ? '✓ तथ्य और कमियाँ' : '✓ FACTS & GAPS'}</span><span>{locale === 'hi' ? '✓ स्रोत संकेत' : '✓ SOURCE LEADS'}</span><b>{locale === 'hi' ? 'मानवीय निर्णय आवश्यक' : 'HUMAN DECISION REQUIRED'}</b></div>
              </article>
            </div>
          </div>
        </section>

        <section className="public-landing__cta">
          <div><div className="public-landing__eyebrow">{locale === 'hi' ? 'आपका अगला कदम यहाँ से शुरू होता है' : 'Your next step starts here'}</div><h2>{translate('Know your route.', locale)}<br /><em>{translate('Make your next move.', locale)}</em></h2><p>{locale === 'hi' ? 'अपने लक्ष्य से शुरू करें। PermitPilot शुरुआती प्रश्नों और उपलब्ध प्रमाणों को व्यवस्थित करने में मदद करेगा।' : 'Start with what you are trying to achieve. PermitPilot will help you organize the first questions and available evidence.'}</p></div>
          <div className="public-landing__cta-actions">
            <button className="public-landing__button public-landing__button--dark" onClick={() => onOpenWorkspace('agent')}>{translate('Find my starting point', locale)} <ArrowRight size={16} /></button>
            <button className="public-landing__button public-landing__button--outline" onClick={() => onOpenWorkspace('membership')}>{translate('Explore membership', locale)} <ArrowRight size={15} /></button>
          </div>
        </section>
      </main>
      <footer className="public-landing__footer">
        <div className="public-landing__footer-main">
          <a href="#landing-top" className="public-landing__brand" aria-label={translate('PermitPilot home', locale)}><img className="public-landing__brand-logo" src={permitpilotLogo} alt="" /></a>
          <span className="public-landing__footer-note">{locale === 'hi' ? 'जटिल अनुमतियों के लिए स्पष्ट रास्ता' : 'A CLEARER ROUTE THROUGH COMPLEX APPROVALS'}</span>
          <nav aria-label={translate('Footer navigation', locale)}><a href="#approach">{translate('Approach', locale)}</a><a href="#journey">{translate('Journey', locale)}</a><button onClick={() => onOpenWorkspace('membership')}>{translate('Membership', locale)}</button><a href="#landing-top">{translate('Back to top ↑', locale)}</a></nav>
        </div>
        <p>{locale === 'hi' ? 'प्रोटोटाइप सीमा: सार्वजनिक स्रोतों का कवरेज चुनिंदा है। शोध संकेत कानूनी सलाह नहीं हैं। आधिकारिक आवश्यकताओं, फ़ॉर्म, आवेदन और अनुमतियों की संबंधित प्राधिकरण से पुष्टि करें।' : 'Prototype limitation: public-source coverage is selective. Research leads are not legal advice. Official requirements, forms, filings, and approvals must be verified with the relevant authority.'}</p>
      </footer>
    </div>
  )
}

export default LandingPage
