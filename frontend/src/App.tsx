import { useEffect, useRef, useState, type FormEvent } from 'react'
import {
  ArrowRight,
  Bell,
  Bot,
  Building2,
  Camera,
  ChevronDown,
  CircleGauge,
  Check,
  CreditCard,
  FileCheck2,
  FileText,
  Files,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Send,
  Radar as RadarIcon,
  Search,
  ScanLine,
  Settings,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react'
import './App.css'
import permitpilotLogo from './assets/permitpilot-logo.png'
import LandingPage from './LandingPage'
import LanguageVoiceControls from './components/LanguageVoiceControls'
import { ACCESS_REQUIRED_EVENT, API_BASE, api, downloadFile, downloadPostFile, getActiveBusinessId, getWorkspaceId, setActiveWorkspaceId, uploadFile } from './lib/api'
import { translate, type Locale } from './lib/i18n'

type View = 'overview' | 'agent' | 'onboarding' | 'compliance' | 'documents' | 'tasks' | 'radar' | 'simulator' | 'reports' | 'membership' | 'settings'
const PRIVATE_DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

function Logo() {
  return (
    <div className="logo">
      <img className="logo-image" src={permitpilotLogo} alt="PermitPilot" />
    </div>
  )
}

function Sidebar({ view, setView, workspaceName, locale }: { view: View; setView: (view: View) => void; workspaceName: string; locale: Locale }) {
  const items = [
    { id: 'overview' as View, label: 'Overview', icon: LayoutDashboard },
    { id: 'agent' as View, label: 'Red Tape Agent', icon: Bot },
    { id: 'onboarding' as View, label: 'Business DNA', icon: Building2 },
    { id: 'compliance' as View, label: 'Compliance', icon: ShieldCheck },
    { id: 'documents' as View, label: 'Documents', icon: Files },
    { id: 'tasks' as View, label: 'Tasks & deadlines', icon: ListChecks },
    { id: 'reports' as View, label: 'Reports', icon: FileText },
    { id: 'membership' as View, label: 'Membership', icon: CreditCard },
  ]
  return (
    <aside className="sidebar">
      <Logo />
      <nav>
        {items.map(({ id, label, icon: Icon }) => (
          <button className={view === id ? 'nav-item active' : 'nav-item'} onClick={() => setView(id)} key={id}>
            <Icon size={18} />
            <span>{translate(label, locale)}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <button className={view === 'settings' ? 'nav-item active' : 'nav-item'} onClick={() => setView('settings')}><Settings size={18} /><span>{translate('Settings', locale)}</span></button>
        <div className="workspace-card">
          <div className="workspace-avatar">{workspaceName.split(/\s+/).slice(0, 2).map((part) => part[0] || '').join('').toUpperCase()}</div>
          <div><strong>{workspaceName}</strong><span>{translate('West Bengal', locale)}</span></div>
          <ChevronDown size={15} />
        </div>
      </div>
    </aside>
  )
}

function Topbar({ openMobile, setView, locale, onLocaleChange, onLockDemo }: { openMobile: () => void; setView: (view: View) => void; locale: Locale; onLocaleChange: (locale: Locale) => void; onLockDemo?: () => void }) {
  const [query, setQuery] = useState('')
  const [noticeOpen, setNoticeOpen] = useState(false)
  const [notifications, setNotifications] = useState<any[]>([])
  const [notificationError, setNotificationError] = useState('')
  const searchInput = useRef<HTMLInputElement>(null)
  const unreadNotifications = notifications.filter((item) => !item.read)

  useEffect(() => {
    let active = true
    api<{items?:any[]}>(`/api/v1/notifications?workspace_id=${encodeURIComponent(getWorkspaceId())}`)
      .then((data) => { if (active) setNotifications(data.items || []) })
      .catch((error) => { if (active) setNotificationError(error instanceof Error ? error.message : 'Could not load notifications') })
    return () => { active = false }
  }, [])
  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        searchInput.current?.focus()
      }
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  const searchItems: Array<[string, View]> = [
    [translate('Overview', locale), 'overview'],
    [translate('Red Tape Agent', locale), 'agent'],
    [translate('Business DNA', locale), 'onboarding'],
    [translate('Compliance', locale), 'compliance'],
    [translate('Documents', locale), 'documents'],
    [translate('Tasks & deadlines', locale), 'tasks'],
    [translate('Reports', locale), 'reports'],
    [translate('Membership', locale), 'membership'],
    [translate('Settings', locale), 'settings'],
    ['Regulatory source checks', 'radar'],
    ['What-if scenario', 'simulator'],
  ]
  const matches = searchItems.filter(([name]) => name.toLowerCase().includes(query.toLowerCase()))

  const markNotificationRead = async (notificationId: string) => {
    setNotificationError('')
    try {
      await api(`/api/v1/notifications/${encodeURIComponent(notificationId)}/read`, { method: 'POST' })
      setNotifications((current) => current.map((item) => item.id === notificationId ? { ...item, read: 1 } : item))
    } catch (error) {
      setNotificationError(error instanceof Error ? error.message : 'Could not mark notification read')
    }
  }

  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={openMobile} aria-label={translate('Open navigation', locale)}><Menu size={20} /></button>
      <div className="search">
        <Search size={16} />
        <input ref={searchInput} aria-label={translate('Search', locale)} value={query} onChange={(event) => setQuery(event.target.value)} placeholder={translate('Search pages and workflows...', locale)} />
        <kbd>CTRL / CMD K</kbd>
        {query && <div className="search-results">{matches.length ? matches.map(([name,id]) => <button key={name} onClick={() => { setView(id); setQuery('') }}><Search size={12} />{name}</button>) : <span>{translate('No results', locale)}</span>}</div>}
      </div>
      <div className="topbar-actions">
        <LanguageVoiceControls locale={locale} onLocaleChange={onLocaleChange} targetSelector=".workspace-content" />
        <button className="icon-button" aria-label={translate('Notifications', locale)} aria-expanded={noticeOpen} onClick={() => setNoticeOpen(!noticeOpen)}><Bell size={18} />{unreadNotifications.length > 0 && <span className="notification-dot" />}</button>
        {onLockDemo && <button className="demo-lock-button" onClick={onLockDemo}><LogOut size={15} /><span>{translate('Lock demo', locale)}</span></button>}
        <div className="profile"><div className="profile-avatar">ME</div><div><strong>{translate(PRIVATE_DEMO_MODE ? 'Private demo' : 'Local workspace', locale)}</strong><span>{translate(PRIVATE_DEMO_MODE ? 'Restricted preview' : 'Single-user mode', locale)}</span></div></div>
      </div>
      {noticeOpen && <div className="notice-panel"><p className="eyebrow">{translate('UNREAD NOTIFICATIONS', locale)}</p>{notificationError && <p className="agent-error">{translate(notificationError, locale)}</p>}{unreadNotifications.length ? unreadNotifications.map((item) => <div key={item.id}><strong>{item.title}</strong><span>{item.detail}</span><button onClick={() => void markNotificationRead(item.id)}>{translate('Mark read', locale)}</button></div>) : !notificationError && <span>{translate('No unread notifications', locale)}</span>}</div>}
    </header>
  )
}

function PrivateDemoGate({ locale, status, error, onLocaleChange, onRetry, onUnlock }: {
  locale: Locale
  status: 'checking' | 'locked' | 'error'
  error: string
  onLocaleChange: (locale: Locale) => void
  onRetry: () => void
  onUnlock: (event: FormEvent<HTMLFormElement>) => void
}) {
  return (
    <main className="auth-screen demo-access-screen">
      <section className="auth-card demo-access-card">
        <div className="demo-access-heading">
          <img src={permitpilotLogo} alt="PermitPilot" />
          <button type="button" className="demo-locale-toggle" onClick={() => onLocaleChange(locale === 'en' ? 'hi' : 'en')}>
            {locale === 'en' ? 'हिन्दी' : 'English'}
          </button>
        </div>
        <p className="eyebrow">{translate('PRIVATE PITCH DEMO', locale)}</p>
        <h1>{translate(status === 'checking' ? 'Checking demo access...' : status === 'error' ? 'Demo connection unavailable' : 'Enter demo access code', locale)}</h1>
        {status === 'checking' ? (
          <p>{translate('Checking access...', locale)}</p>
        ) : status === 'error' ? (
          <>
            <p className="auth-error">{translate(error, locale)}</p>
            <button type="button" className="demo-submit" onClick={onRetry}>{translate('Retry connection', locale)}</button>
          </>
        ) : (
          <>
            <p>{translate('This private demo uses one shared workspace. Use synthetic business data only.', locale)}</p>
            {error && <p className="auth-error" role="alert">{translate(error, locale)}</p>}
            <form onSubmit={onUnlock}>
              <label htmlFor="demo-access-code">{translate('Access code', locale)}</label>
              <input id="demo-access-code" name="demo-access-code" type="password" autoComplete="current-password" maxLength={256} required />
              <button className="demo-submit" type="submit">{translate('Unlock workspace', locale)}</button>
            </form>
          </>
        )}
      </section>
    </main>
  )
}

function Overview({ setView, locale }: { setView: (view: View) => void; locale: Locale }) {
  const [profile, setProfile] = useState<any>(null)
  const [requirementsList, setRequirementsList] = useState<any[]>([])
  const [updates, setUpdates] = useState<any[]>([])
  const [dashboardError, setDashboardError] = useState('')
  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const data = await api<{updates?:any[]}>('/api/v1/regulatory/updates')
        if (active) setUpdates(data.updates || [])
      } catch (error) {
        if (active) setDashboardError(error instanceof Error ? error.message : 'Could not load source records')
      }
      try {
        const businessId = await getActiveBusinessId()
        if (!businessId) return
        const [profileData, assessmentData] = await Promise.all([
          api<{items?:any[]}>(`/api/v1/businesses/${encodeURIComponent(businessId)}/profile-history`),
          api<{results?:any[]}>(`/api/v1/businesses/${encodeURIComponent(businessId)}/requirements`),
        ])
        if (active) {
          setProfile(profileData.items?.[0]?.facts || null)
          setRequirementsList(assessmentData.results || [])
        }
      } catch (error) {
        if (active) setDashboardError(error instanceof Error ? error.message : 'Could not load business assessment')
      }
    }
    void load()
    return () => { active = false }
  }, [])
  const hour = new Date().getHours()
  const greeting = translate(hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening', locale)
  const businessName = profile?.business_name || localStorage.getItem('permitpilot-workspace-name') || translate('Your workspace', locale)
  const confirmedCount = Object.values(profile || {}).filter((value) => value !== null && value !== undefined).length
  const readiness = profile ? Math.min(100, Math.round((confirmedCount / 9) * 100)) : 0
  const applicable = requirementsList.filter((item) => item.status === 'APPLICABLE').length
  const conditional = requirementsList.filter((item) => item.status === 'CONDITIONAL').length
  const unresolved = requirementsList.filter((item) => item.status === 'UNRESOLVED').length
  return (
    <>
      <div className="page-heading">
        <div><p className="eyebrow">{new Date().toLocaleDateString(locale === 'hi' ? 'hi-IN' : 'en-IN', { weekday: 'long', day: '2-digit', month: 'long' })}</p><h1>{greeting}!</h1><p className="dashboard-context">{translate('Workspace:', locale)} {businessName}</p></div>
      </div>
      {dashboardError && <div className="agent-error">{dashboardError}</div>}
      <section className="metrics" aria-label={translate('Compliance summary', locale)}>
        <article><span className="metric-icon lime"><ShieldCheck size={18} /></span><div><strong>{applicable}</strong><p>{translate('Applicable', locale)}</p></div></article>
        <article><span className="metric-icon amber"><CircleGauge size={18} /></span><div><strong>{conditional}</strong><p>{translate('Conditional', locale)}</p></div></article>
        <article><span className="metric-icon violet"><FileCheck2 size={18} /></span><div><strong>{unresolved}</strong><p>{translate('Unresolved', locale)}</p></div></article>
        <article><span className="metric-icon blue"><RadarIcon size={18} /></span><div><strong>{updates.length}</strong><p>{translate('Regulatory updates', locale)}</p></div></article>
      </section>
      <section className="dashboard-grid">
        <article className="panel next-action">
          <div className="panel-heading"><div><p className="eyebrow">{translate('NEXT BEST ACTION', locale)}</p><h2>{translate(!profile ? 'Start with your business profile.' : profile?.annual_turnover ? 'Review candidate sources.' : 'Complete a missing fact.', locale)}</h2></div><span className="priority">{translate(profile?.annual_turnover ? 'Medium priority' : 'High priority', locale)}</span></div>
          <div className="action-content">
            <div className="action-number">01</div>
            <div><h3>{translate(!profile ? 'Describe your business' : profile?.annual_turnover ? 'Review candidate requirements' : 'Confirm a missing fact', locale)}</h3><p>{!profile ? translate('No business facts or sector-specific requirements are assumed yet.', locale) : profile?.annual_turnover ? locale === 'hi' ? `${businessName} के स्रोत प्रमाण देखें; संभावित नियमों की पुष्टि आवश्यक है।` : `Review source evidence for ${businessName}; candidate rules still require verification.` : translate('Add missing facts to evaluate candidate checks.', locale)}</p><button className="text-button" onClick={() => setView(!profile ? 'onboarding' : profile?.annual_turnover ? 'compliance' : 'onboarding')}>{translate(!profile ? 'Set up Business DNA' : profile?.annual_turnover ? 'Open compliance' : 'Confirm business facts', locale)} <ArrowRight size={15} /></button></div>
          </div>
        </article>
        <article className="panel readiness">
          <div className="panel-heading"><div><p className="eyebrow">{translate('READINESS', locale)}</p><h2>{readiness}%</h2></div><span className="trend">{translate(profile ? 'Profile saved' : 'Setup needed', locale)}</span></div>
          <div className="ring" aria-label={locale === 'hi' ? `तैयारी ${readiness} प्रतिशत` : `${readiness} percent readiness`} style={{ background: `conic-gradient(#a7bd18 0 ${readiness}%,#edf0e4 ${readiness}% 100%)` }}><span>{readiness}</span></div>
          <p className="ring-caption">{translate(profile ? 'Confirmed profile available' : 'Complete business setup', locale)}</p>
        </article>
        <article className="panel requirements-panel">
          <div className="panel-heading"><div><p className="eyebrow">{translate('TOP REQUIREMENTS', locale)}</p><h2>{translate('Needs your attention', locale)}</h2></div><button className="text-button" onClick={() => setView('compliance')}>{translate('View all', locale)} <ArrowRight size={15} /></button></div>
          <div className="requirement-list">
            {(requirementsList.length ? requirementsList : [{rule_id:'SETUP-001',title:'Complete business setup',authority:'PermitPilot',status:'UNRESOLVED'}]).slice(0,3).map((item) => (
              <button className="requirement-row" key={item.rule_id || item.id} onClick={() => setView('compliance')}>
                <span className={`status-dot ${item.status === 'APPLICABLE' ? 'lime' : item.status === 'CONDITIONAL' ? 'amber' : 'violet'}`} />
                <div><strong>{item.title}</strong><span>{item.authority} · {item.rule_id || item.id}</span></div>
                <span className={`status-badge ${item.status === 'APPLICABLE' ? 'lime' : item.status === 'CONDITIONAL' ? 'amber' : 'violet'}`}>{translate(item.status, locale)}</span>
                <ChevronDown size={16} />
              </button>
            ))}
          </div>
        </article>
        <article className="panel radar-panel">
          <div className="panel-heading"><div><p className="eyebrow">{translate('REGULATORY RADAR', locale)}</p><h2>{translate('Recent signal', locale)}</h2></div><span className="live"><i /> {updates.length} {locale === 'hi' ? 'स्रोत' : 'source'}</span></div>
          <div className="radar-feature">
            <div className="radar-icon"><RadarIcon size={26} /></div>
            <div><span>{updates[0]?.jurisdiction || 'WEST BENGAL'} · {locale === 'hi' ? 'स्रोत जाँच' : 'SOURCE CHECK'}</span><h3>{updates[0]?.title || translate('No source update recorded', locale)}</h3><p>{updates[0]?.authority ? `${locale === 'hi' ? 'प्राधिकरण' : 'Authority'}: ${updates[0].authority}` : translate('Run a source scan to identify changes.', locale)}</p></div>
          </div>
          <button className="text-button" onClick={() => setView('radar')}>{translate('Inspect evidence', locale)} <ArrowRight size={15} /></button>
        </article>
      </section>
    </>
  )
}

function Compliance({ locale }: { locale: Locale }) {
  const [requirementItems, setRequirementItems] = useState<any[]>([])
  const [selected, setSelected] = useState<any>(null)
  const [assessmentId, setAssessmentId] = useState<string | null>(null)
  const [rerunning, setRerunning] = useState(false)
  const [qaQuestion, setQaQuestion] = useState('')
  const [qaAnswer, setQaAnswer] = useState('')
  const [qaEvidence, setQaEvidence] = useState<string[]>([])
  const [qaProvider, setQaProvider] = useState('')
  const [qaProviderError, setQaProviderError] = useState('')
  const [qaLoading, setQaLoading] = useState(false)
  const [qaError, setQaError] = useState('')
  const [complianceError, setComplianceError] = useState('')
  const mapRequirements = (results: any[]) => results.map((item: any) => ({
    id: item.rule_id,
    title: item.title,
    authority: item.authority,
    status: item.status,
    accent: item.status === 'APPLICABLE' ? 'lime' : item.status === 'CONDITIONAL' ? 'amber' : 'violet',
    detail: item.disclaimer || 'Review this result against the current confirmed facts and official source evidence.',
    jurisdiction: item.jurisdiction,
    source_type: item.source_type,
    missing_facts: item.missing_facts || [],
    source: item.source,
  }))

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const businessId = await getActiveBusinessId()
        if (!businessId) {
          if (active) setComplianceError('Create and confirm a Business DNA profile before running an assessment.')
          return
        }
        const data = await api<any>(`/api/v1/businesses/${encodeURIComponent(businessId)}/requirements`)
        if (!active) return
        setAssessmentId(data.assessment_id || null)
        const mapped = mapRequirements(data.results || [])
        setRequirementItems(mapped)
        setSelected(mapped[0] || null)
      } catch (error) {
        if (active) setComplianceError(error instanceof Error ? error.message : 'Could not load assessment results')
      }
    }
    void load()
    return () => { active = false }
  }, [])
  const rerun = async () => {
    setRerunning(true)
    setComplianceError('')
    try {
      const businessId = await getActiveBusinessId()
      if (!businessId) throw new Error('Create a business before running an assessment')
      const data = await api<any>(`/api/v1/assessments?business_id=${encodeURIComponent(businessId)}`, { method: 'POST' })
      setAssessmentId(data.assessment_id || null)
      const mapped = mapRequirements(data.results || [])
      setRequirementItems(mapped)
      setSelected(mapped[0] || null)
    } catch (error) {
      setComplianceError(error instanceof Error ? error.message : 'Could not run assessment')
    } finally {
      setRerunning(false)
    }
  }

  const askQuestion = async () => {
    if (!qaQuestion.trim() || !selected || !assessmentId) return
    setQaLoading(true)
    setQaError('')
    setQaAnswer('')
    setQaEvidence([])
    setQaProvider('')
    setQaProviderError('')
    try {
      const response = await api<any>('/api/v1/requirements/question', {
        method: 'POST',
        body: JSON.stringify({
          assessment_id: assessmentId,
          rule_id: selected.id,
          question: qaQuestion.trim(),
        }),
      })
      setQaAnswer(response.answer || 'No answer was returned. Review the saved source evidence.')
      setQaProvider(response.provider || '')
      setQaProviderError(response.provider_error || '')
      const evidence = [
        ...(Array.isArray(response.evidence_used) ? response.evidence_used : []),
        ...(Array.isArray(response.missing_information) ? response.missing_information.map((fact: string) => `Missing information: ${fact}`) : []),
      ]
      setQaEvidence(evidence.filter((item: unknown): item is string => typeof item === 'string'))
    } catch (error) {
      setQaError(error instanceof Error ? error.message : 'Could not answer this question')
    } finally {
      setQaLoading(false)
    }
  }
  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">{translate('BUSINESS PROFILE · ASSESSMENT', locale)}</p><h1>{translate('Compliance', locale)}</h1></div><button className="primary-button" onClick={rerun} disabled={rerunning}><ShieldCheck size={16} /> {translate(rerunning ? 'Evaluating...' : 'Re-run assessment', locale)}</button></div>
      {complianceError && <div className="agent-error">{translate(complianceError, locale)}</div>}
      <div className="compliance-layout">
        <section className="panel requirement-detail">
          {!selected ? <div className="empty-list">{translate('No assessed requirements yet. Add and confirm a business profile before checking applicability. No sector-specific requirements are assumed.', locale)}</div> : <>
          <div className="detail-title"><div><p className="eyebrow">{selected.id}</p><h2>{selected.title}</h2></div><span className={`status-badge ${selected.accent}`}>{translate(selected.status, locale)}</span></div>
          <div className="explanation"><p className="eyebrow">{translate('WHY THIS APPEARS', locale)}</p><h3>{translate(selected.detail, locale)}</h3></div>
          <div className="detail-columns">
            <div><p className="eyebrow">{translate('REQUIREMENT', locale)}</p><ul><li>{translate('Applicability', locale)}: {translate(selected.status, locale)}</li><li>{translate('Jurisdiction', locale)}: {selected.jurisdiction || translate('West Bengal, India', locale)}</li><li>{translate('Missing facts', locale)}: {selected.missing_facts.length ? selected.missing_facts.join(', ') : translate('None listed', locale)}</li></ul></div>
            <div><p className="eyebrow">{translate('SOURCE EVIDENCE', locale)}</p><div className="source-card"><span>{translate(selected.source_type || 'CANDIDATE', locale)}</span><strong>{selected.authority}</strong><p>{selected.source || translate('Official source verification is pending.', locale)}</p></div></div>
          </div>
          <div className="grounded-qa"><div><ShieldCheck size={17} /><strong>{translate('Ask PermitPilot', locale)}</strong></div><input value={qaQuestion} onChange={(event) => setQaQuestion(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && void askQuestion()} placeholder={locale === 'hi' ? `${selected.title} के बारे में पूछें...` : `${translate('Ask about', locale)} ${selected.title}...`} disabled={!assessmentId || qaLoading} /><button aria-label={translate('Send', locale)} onClick={() => void askQuestion()} disabled={!qaQuestion.trim() || !assessmentId || qaLoading}><ArrowRight size={16} /></button></div>
          {qaError && <div className="agent-error">{translate(qaError, locale)}</div>}
          {qaLoading && <div className="empty-list">{translate('Checking the saved assessment and evidence...', locale)}</div>}
          {qaAnswer && <div className="qa-answer">{qaProvider === 'evidence_fallback' && <strong className="qa-fallback-badge">{translate('AI UNAVAILABLE · STORED EVIDENCE SUMMARY', locale)}</strong>}<p>{qaAnswer}</p>{qaProviderError && <small>{translate(qaProviderError, locale)}</small>}{qaEvidence.length > 0 && <small>{translate('Evidence used', locale)}: {qaEvidence.join('; ')}</small>}</div>}
          </>}
        </section>
        <aside className="panel requirement-browser">
          <div className="panel-heading"><h3>{translate('Requirements', locale)}</h3><span>{requirementItems.length}</span></div>
          {!requirementItems.length && <div className="empty-list">{translate('No assessment results to display.', locale)}</div>}
          {requirementItems.map((item) => (
            <button className={selected?.id === item.id ? 'browser-item selected' : 'browser-item'} onClick={() => setSelected(item)} key={item.id}>
              <span className={`status-dot ${item.accent}`} /><div><strong>{item.title}</strong><span>{translate(item.status, locale)}</span></div>
            </button>
          ))}
        </aside>
      </div>
    </>
  )
}

function Onboarding({ locale }: { locale: Locale }) {
  const [step, setStep] = useState(2)
  const [businessId, setBusinessId] = useState<string | null>(null)
  const [businessError, setBusinessError] = useState('')
  const [turnover, setTurnover] = useState('')
  const [saving, setSaving] = useState(false)
  const [description, setDescription] = useState('')
  const [extracting, setExtracting] = useState(false)
  const [extractedFacts, setExtractedFacts] = useState<any>(null)
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const workspaceId = getWorkspaceId()
        const data = await api<{items:any[]}>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/businesses`)
        const business = data.items[0]
        if (!business) {
          if (!cancelled) setBusinessId(null)
          return
        }
        if (!cancelled) setBusinessId(business.id)
        const history = await api<{items:any[]}>(`/api/v1/businesses/${encodeURIComponent(business.id)}/profile-history`)
        const latest = history.items?.[0]
        if (!cancelled && latest?.facts) {
          setDescription(latest.original_description || '')
          setExtractedFacts(latest.facts)
          setTurnover(latest.facts.annual_turnover == null ? '' : String(latest.facts.annual_turnover))
          setStep(3)
        }
      } catch (error) {
        if (!cancelled) setBusinessError(error instanceof Error ? error.message : 'Could not load business')
      }
    }
    load()
    return () => { cancelled = true }
  }, [])
  const ensureBusiness = async () => {
    if (businessId) return businessId
    const workspaceId = getWorkspaceId()
    const data = await api<any>('/api/v1/businesses', {
      method: 'POST',
      body: JSON.stringify({
        workspace_id: workspaceId,
        business_name: extractedFacts?.business_name || 'Unnamed business',
        business_type: extractedFacts?.business_type || null,
        country: 'India',
        state: 'West Bengal',
        city: extractedFacts?.city || null,
        original_description: description,
      }),
    })
    setBusinessId(data.business_id)
    return data.business_id
  }
  const updateCandidateFact = (field: string, value: any) => {
    setExtractedFacts((current: any) => ({ ...(current || {}), [field]: value }))
    setStep(2)
  }
  const extractFacts = async () => {
    if (!description.trim()) {
      setBusinessError(translate('Describe your business before extracting candidate facts.', locale))
      return
    }
    setExtracting(true)
    setBusinessError('')
    try {
      const targetBusinessId = await ensureBusiness()
      const data = await api<any>(`/api/v1/businesses/${encodeURIComponent(targetBusinessId)}/extract-facts?description=${encodeURIComponent(description)}`, { method: 'POST' })
      const facts = data.facts
      setExtractedFacts(facts)
      if (facts?.annual_turnover) setTurnover(String(facts.annual_turnover))
      setStep(2)
    } catch (error) {
      setBusinessError(error instanceof Error ? error.message : 'Could not extract candidate facts')
    } finally {
      setExtracting(false)
    }
  }
  const confirmProfile = async () => {
    const activities = Array.isArray(extractedFacts?.activities)
      ? extractedFacts.activities.filter((value: string) => value.trim())
      : []
    const requiredFacts = [
      extractedFacts?.business_name?.trim(),
      extractedFacts?.business_type?.trim(),
      extractedFacts?.city?.trim(),
      extractedFacts?.premises?.trim(),
      activities.length > 0,
    ]
    if (!description.trim() || !extractedFacts || requiredFacts.some((value) => !value)) {
      setBusinessError(translate('Describe the business and provide its name, type, city, operating model, and at least one activity before saving.', locale))
      return
    }
    setSaving(true)
    setBusinessError('')
    try {
      const targetBusinessId = await ensureBusiness()
      await api(`/api/v1/businesses/${encodeURIComponent(targetBusinessId)}/confirm-profile`, {
        method: 'POST',
        body: JSON.stringify({
          original_description: description,
          facts: {
            business_name: extractedFacts?.business_name || 'Unnamed business',
            business_type: extractedFacts?.business_type || 'small_business',
            country: 'India',
            state: 'West Bengal',
            city: extractedFacts?.city || 'West Bengal',
            activities,
            premises: extractedFacts?.premises || 'commercial_premises',
            employee_count: extractedFacts?.employee_count ?? null,
            annual_turnover: turnover ? Number(turnover.replace(/[^0-9]/g, '')) : null,
            source_description: description,
          },
        }),
      })
      setStep(3)
    } catch (error) {
      setBusinessError(error instanceof Error ? error.message : 'Could not confirm profile')
    } finally {
      setSaving(false)
    }
  }
  const facts = [
    [translate('Business name', locale), 'business_name', extractedFacts?.business_name || ''],
    [translate('Business type', locale), 'business_type', extractedFacts?.business_type || ''],
    [translate('City', locale), 'city', extractedFacts?.city || ''],
    [translate('Operating model', locale), 'premises', extractedFacts?.premises || ''],
    [translate('Activities (comma-separated)', locale), 'activities', Array.isArray(extractedFacts?.activities) ? extractedFacts.activities.join(', ') : ''],
    [translate('Employees', locale), 'employee_count', extractedFacts?.employee_count ?? ''],
    [translate('Annual turnover (INR)', locale), 'annual_turnover', turnover],
  ]
  const foodActivityIdentified = [
    ...(Array.isArray(extractedFacts?.activities) ? extractedFacts.activities : []),
    extractedFacts?.business_type || '',
  ].some((value: string) => /food|baking|cooking|catering|restaurant|bakery/i.test(value))
  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">{translate('PROFILE REVISION', locale)}</p><h1>{translate('Business DNA', locale)}</h1></div><button className="primary-button" onClick={confirmProfile} disabled={saving || extracting}>{translate(saving ? 'Saving...' : 'Confirm profile', locale)}</button></div>
      <div className="onboarding-layout">
        <aside className="panel profile-progress">
          <p className="eyebrow">{translate('ONBOARDING', locale)}</p>
          {([['01','Describe','Complete'],['02','Review facts','In progress'],['03','Assess','Next']] as const).map(([number,title,state]) => (
            <div className={number === '02' ? 'progress-step active' : 'progress-step'} key={number}><span>{number}</span><div><strong>{translate(title, locale)}</strong><small>{translate(state, locale)}</small></div></div>
          ))}
        </aside>
        <section className="panel fact-review">
          <div className="panel-heading"><div><p className="eyebrow">{translate('BUSINESS FACT REVIEW', locale)}</p><h2>{translate('Review before assessment', locale)}</h2></div><span className="review-count">{translate(step === 3 ? 'Profile saved' : extractedFacts ? 'Facts need your review' : 'No facts entered', locale)}</span></div>
          <div className="profile-description"><label>{translate('Natural-language business description', locale)}<textarea value={description} onChange={(event) => { setDescription(event.target.value); setStep(2) }} placeholder={translate('Describe any business: what it does, where it operates, and how it operates.', locale)} /></label><button className="secondary-button" onClick={extractFacts} disabled={extracting}>{translate(extracting ? 'Extracting...' : 'Extract facts', locale)}</button></div>
          <p className="agent-disclaimer">{translate('Extracted or manually entered values are candidates, not confirmed facts. Review them and then save. Source coverage currently applies only to selected West Bengal portals.', locale)}</p>
          {businessError && <div className="agent-error">{translate(businessError, locale)}</div>}
          <div className="fact-grid">
            {facts.map(([label,field,value]) => (
              <label className={field !== 'annual_turnover' && field !== 'employee_count' && !value ? 'fact-card unresolved' : 'fact-card'} key={field}>
                <span>{label}</span>
                <input
                  aria-label={label}
                  type={field === 'employee_count' || field === 'annual_turnover' ? 'number' : 'text'}
                  min={field === 'employee_count' || field === 'annual_turnover' ? 0 : undefined}
                  value={value}
                  placeholder={translate(field === 'annual_turnover' || field === 'employee_count' ? 'Optional' : 'Enter a value', locale)}
                  onChange={(event) => {
                    if (field === 'annual_turnover') {
                      setTurnover(event.target.value)
                      setStep(2)
                    } else if (field === 'employee_count') {
                      updateCandidateFact(field, event.target.value ? Number(event.target.value) : null)
                    } else if (field === 'activities') {
                      updateCandidateFact(field, event.target.value.split(',').map((item) => item.trim()).filter(Boolean))
                    } else {
                      updateCandidateFact(field, event.target.value)
                    }
                  }}
                />
                <small>{translate(field === 'annual_turnover' || field === 'employee_count' ? 'Optional' : step === 3 ? 'Saved' : value ? 'Review candidate' : 'Required input', locale)}</small>
              </label>
            ))}
          </div>
          <section className="identity-preview" aria-labelledby="identity-preview-title">
            <div className="identity-preview__heading">
              <div><p className="eyebrow">{translate('DIGILOCKER · NATIONAL GATEWAY', locale)}</p><h2 id="identity-preview-title">{translate('DigiLocker identity preview', locale)}</h2><p>{translate('Secure identity verification is not connected in this demo.', locale)}</p></div>
              <span className="preview-stamp">{translate('PREVIEW · NO IDENTITY DATA', locale)}</span>
            </div>
            <div className="identity-preview__fields">
              {[
                ['Verified name', 'Not connected'],
                ['Date of birth', 'Not shared'],
                ['Aadhaar status', 'No Aadhaar data'],
                ['PAN status', 'No PAN data'],
                ['Verified address', 'Not available'],
              ].map(([label, value]) => <div className="identity-preview__field" key={label}><span>{translate(label, locale)}</span><strong>{translate(value, locale)}</strong></div>)}
            </div>
            <div className={`identity-preview__check ${foodActivityIdentified ? 'identity-preview__check--food' : ''}`}>
              <ShieldCheck size={19} />
              <div><strong>{translate('FSSAI candidate check', locale)}</strong><p>{translate(foodActivityIdentified ? 'Food activity appears in this draft profile. Verify any FSSAI requirement with the authority.' : 'No food activity is confirmed. FSSAI requirements are not assumed for this profile.', locale)}</p></div>
            </div>
            <div className="identity-preview__actions">
              <button className="secondary-button" disabled><ArrowRight size={15} /> {translate('Redirect to DigiLocker & fetch ID', locale)}</button>
              <button className="text-button" disabled>{translate('Apply to Business DNA', locale)}</button>
            </div>
            <p className="agent-disclaimer">{translate('Front-end preview only. No DigiLocker redirect, identity verification, ID retrieval, or profile update occurs.', locale)}</p>
          </section>
          {step === 3 && <div className="profile-saved"><Check size={17} /> {translate('Profile revision saved. Assessment inputs are ready.', locale)}</div>}
        </section>
      </div>
    </>
  )
}

function Reports({ locale }: { locale: Locale }) {
  const [profile, setProfile] = useState<any>(null)
  const [assessment, setAssessment] = useState<any>(null)
  const [businessId, setBusinessId] = useState<string | null>(null)
  const [reports, setReports] = useState<any[]>([])
  const [reportError, setReportError] = useState('')
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)

  const loadReports = async () => {
    setLoading(true)
    setReportError('')
    try {
      const workspaceId = getWorkspaceId()
      const [businessData, reportData] = await Promise.all([
        api<{items:any[]}>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/businesses`),
        api<{items:any[]}>(`/api/v1/reports?workspace_id=${encodeURIComponent(workspaceId)}`),
      ])
      const activeBusinessId = businessData.items[0]?.id || null
      setBusinessId(activeBusinessId)
      setReports(reportData.items || [])
      if (!activeBusinessId) {
        setProfile(null)
        setAssessment(null)
        return
      }
      const [profileData, assessmentData] = await Promise.all([
        api<{items?:any[]}>(`/api/v1/businesses/${encodeURIComponent(activeBusinessId)}/profile-history`),
        api<any>(`/api/v1/businesses/${encodeURIComponent(activeBusinessId)}/requirements`),
      ])
      setProfile(profileData.items?.[0]?.facts || null)
      setAssessment(assessmentData)
    } catch (error) {
      setReportError(error instanceof Error ? error.message : 'Could not load reports')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void loadReports() }, [])

  const downloadReport = async (reportId: string) => {
    setReportError('')
    try {
      await downloadFile(`/api/v1/reports/${encodeURIComponent(reportId)}/download`, `permitpilot-report-${reportId}.pdf`)
    } catch (error) {
      setReportError(error instanceof Error ? error.message : 'Could not download report')
    }
  }

  const exportReport = async () => {
    if (!businessId || !assessment?.assessment_id) {
      setReportError('Confirm a business profile and run its assessment before exporting.')
      return
    }
    setExporting(true)
    setReportError('')
    try {
      const report = await api<{report_id:string;assessment_id:string;status:string}>(
        `/api/v1/reports?workspace_id=${encodeURIComponent(getWorkspaceId())}&business_id=${encodeURIComponent(businessId)}`,
        { method: 'POST' },
      )
      setReports((current) => [{
        id: report.report_id,
        report_type: 'assessment_summary',
        assessment_id: report.assessment_id,
        status: report.status,
        created_at: new Date().toISOString(),
      }, ...current])
      await downloadReport(report.report_id)
    } catch (error) {
      setReportError(error instanceof Error ? error.message : 'Could not export report')
    } finally {
      setExporting(false)
    }
  }
  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">{translate('ASSESSMENT 04', locale)}</p><h1>{translate('Reports', locale)}</h1></div><div className="report-actions"><button className="secondary-button" onClick={() => void loadReports()} disabled={loading}>{translate('Refresh', locale)}</button><button className="primary-button" onClick={exportReport} disabled={loading || exporting || !businessId || !assessment?.assessment_id}><FileText size={16} /> {translate(exporting ? 'Exporting...' : 'Export PDF', locale)}</button></div></div>
      {reportError && <div className="agent-error">{translate(reportError, locale)}</div>}
      <section className="report-layout">
        <aside className="panel report-list">
          <p className="eyebrow">{translate('SAVED REPORTS', locale)}</p>
          {loading && <div className="empty-list">{translate('Loading saved reports...', locale)}</div>}
          {!loading && !reports.length && <div className="empty-list">{translate('No reports saved yet. Export the current assessment to create one.', locale)}</div>}
          {reports.map((report) => (
            <button className="report-row" key={report.id} onClick={() => void downloadReport(report.id)}>
              <FileText size={17} />
              <div><strong>{translate(String(report.report_type || 'assessment_summary').replaceAll('_', ' '), locale)}</strong><span>{report.created_at ? new Date(report.created_at).toLocaleString(locale === 'hi' ? 'hi-IN' : 'en-IN') : translate('Date unavailable', locale)} · {translate(report.status, locale)}</span></div>
              <ArrowRight size={14} />
            </button>
          ))}
        </aside>
        <article className="panel report-preview">
          <div className="report-brand"><Logo /><span>{translate('ASSESSMENT SUMMARY', locale)}</span></div>
          <h2>{profile?.business_name || translate('Unconfirmed business', locale)}</h2><p className="report-meta">{profile?.city ? `${profile.city}, ` : ''}{profile?.state || translate('West Bengal', locale)} · {new Date().toLocaleDateString(locale === 'hi' ? 'hi-IN' : 'en-IN')} · {translate('Engine', locale)} rules-engine-local-1.0</p>
          <div className="report-summary"><div><strong>{assessment?.results?.filter((item:any) => item.status === 'APPLICABLE').length || 0}</strong><span>{translate('Applicable', locale)}</span></div><div><strong>{assessment?.results?.filter((item:any) => item.status === 'CONDITIONAL').length || 0}</strong><span>{translate('Conditional', locale)}</span></div><div><strong>{assessment?.results?.filter((item:any) => item.status === 'UNRESOLVED').length || 0}</strong><span>{translate('Unresolved', locale)}</span></div></div>
          <h3>{translate('Key findings', locale)}</h3>
          {(assessment?.results || []).map((item:any) => <div className="report-finding" key={item.rule_id}><span className={`status-dot ${item.status === 'APPLICABLE' ? 'lime' : item.status === 'CONDITIONAL' ? 'amber' : 'violet'}`} /><div><strong>{item.title}</strong><p>{translate(item.disclaimer || '', locale)}</p></div><span className={`status-badge ${item.status === 'APPLICABLE' ? 'lime' : item.status === 'CONDITIONAL' ? 'amber' : 'violet'}`}>{translate(item.status, locale)}</span></div>)}
          {loading && <div className="empty-list">{translate('Loading current assessment...', locale)}</div>}
          {!loading && !assessment?.results?.length && <div className="empty-list">{translate('No assessment results yet. Confirm your profile and run its assessment before exporting.', locale)}</div>}
          <div className="report-disclaimer">{translate('SOURCE VERIFICATION REQUIRED — Verify requirements against current official sources before action. This document is not legal advice.', locale)}</div>
        </article>
      </section>
    </>
  )
}

function SmartOcrPreview({ locale }: { locale: Locale }) {
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const cameraInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!previewUrl) return
    return () => URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  const chooseFile = (nextFile?: File) => {
    if (!nextFile) return
    if (!nextFile.type.startsWith('image/') && nextFile.type !== 'application/pdf') return
    setFile(nextFile)
    setPreviewUrl(URL.createObjectURL(nextFile))
  }

  return (
    <section className="smart-ocr panel">
      <div className="smart-ocr__heading">
        <div><p className="eyebrow">{translate('MULTIMODAL VISION OCR · GEMINI 2.5 FLASH', locale)}</p><h2>{translate('Smart document scan', locale)}</h2><p>{translate('Local preview only · OCR is not connected', locale)}</p></div>
        <div className="smart-ocr__actions">
          <button className="secondary-button" onClick={() => cameraInput.current?.click()}><Camera size={16} /> {translate('Scan camera', locale)}</button>
          <label className="primary-button"><Upload size={16} /> {translate('Upload scan document', locale)}<input type="file" hidden accept="image/*,.pdf,application/pdf" onChange={(event) => { chooseFile(event.target.files?.[0]); event.target.value = '' }} /></label>
          <input ref={cameraInput} type="file" hidden accept="image/*" capture="environment" onChange={(event) => { chooseFile(event.target.files?.[0]); event.target.value = '' }} />
        </div>
      </div>
      <div className="smart-ocr__body">
        <div className="smart-ocr__drop" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); chooseFile(event.dataTransfer.files[0]) }}>
          {file ? (
            <>
              <div className="smart-ocr__file"><ScanLine size={17} /><strong>{file.name}</strong><span>{Math.max(1, Math.ceil(file.size / 1024))} KB</span><button className="text-button" onClick={() => { setFile(null); setPreviewUrl('') }}>{translate('Remove preview', locale)}</button></div>
              {file.type === 'application/pdf' ? <iframe className="smart-ocr__preview" src={previewUrl} title={translate('Local document preview', locale)} /> : <img className="smart-ocr__preview smart-ocr__preview--image" src={previewUrl} alt={translate('Selected document preview', locale)} />}
            </>
          ) : (
            <><ScanLine size={28} /><strong>{translate('Drop a scan or select a file', locale)}</strong><span>{translate('Images and PDF · stays on this device', locale)}</span></>
          )}
        </div>
        <div className="smart-ocr__results">
          <div className="panel-heading"><div><p className="eyebrow">{translate('OCR RESULTS', locale)}</p><h3>{translate('Waiting for a connected OCR service', locale)}</h3></div><span className="candidate-form-status candidate-form-status--unverified">{translate('PREVIEW ONLY', locale)}</span></div>
          <p>{translate('This screen does not extract text or verify a document. Selected files are previewed locally and are not uploaded from this panel.', locale)}</p>
          <div className="smart-ocr__field"><span>{translate('Document type', locale)}</span><strong>{translate('Not processed', locale)}</strong></div>
          <div className="smart-ocr__field"><span>{translate('Detected fields', locale)}</span><strong>—</strong></div>
          <div className="smart-ocr__field"><span>{translate('Identity match', locale)}</span><strong>{translate('Not checked', locale)}</strong></div>
        </div>
      </div>
    </section>
  )
}

function Documents({ locale }: { locale: Locale }) {
  const [documents, setDocuments] = useState<Array<[string,string,string,string]>>([])
  const [toast, setToast] = useState('')
  const [documentError, setDocumentError] = useState('')

  useEffect(() => {
    api<{items:Array<{filename:string;mime_type:string;processing_state:string;created_at:string}>}>(
      `/api/v1/documents?workspace_id=${encodeURIComponent(getWorkspaceId())}`
    ).then((data) => {
      if (data.items.length) {
        setDocuments(data.items.map((document) => [
          document.filename,
          document.mime_type,
          document.processing_state === 'completed' ? 'Reviewed' : 'Uploaded · not processed',
          document.created_at,
        ]))
      }
    }).catch((error) => setDocumentError(error instanceof Error ? error.message : 'Could not load documents'))
  }, [])

  const addDocument = async (file: File) => {
    setDocumentError('')
    try {
      await uploadFile(`/api/v1/documents/upload?workspace_id=${encodeURIComponent(getWorkspaceId())}`, file)
      setDocuments((current) => [[file.name, file.type || 'Evidence upload', 'Uploaded · not processed', 'Just now'], ...current])
      setToast(locale === 'hi' ? `${file.name} अपलोड हुआ। OCR या फ़ॉर्म भरने की प्रक्रिया नहीं हुई।` : `${file.name} uploaded. No OCR or form filling was performed.`)
    } catch (error) {
      setDocumentError(error instanceof Error ? error.message : 'Upload failed')
    }
  }

  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">{translate('EVIDENCE VAULT', locale)}</p><h1>{translate('Documents', locale)}</h1></div><label className="primary-button"><Upload size={16} /> {translate('Upload document', locale)}<input type="file" hidden accept=".pdf,.png,.jpg,.jpeg" onChange={(event) => event.target.files?.[0] && addDocument(event.target.files[0])} /></label></div>
      <SmartOcrPreview locale={locale} />
      <section className="upload-zone" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); const file = event.dataTransfer.files[0]; if (file) addDocument(file) }}>
        <div className="upload-icon"><Upload size={24} /></div><h2>{translate('Drop evidence here', locale)}</h2><p>{translate('PDF, PNG or JPG · up to 10 MB', locale)}</p>
        <label className="secondary-button">{translate('Choose file', locale)}<input type="file" hidden accept=".pdf,.png,.jpg,.jpeg" onChange={(event) => event.target.files?.[0] && addDocument(event.target.files[0])} /></label>
        <p className="agent-disclaimer">{translate('Files are stored in the local workspace for reference. They are not yet read by Compliance or the Review sheet: this prototype does not perform OCR, extract document contents, or fill official forms.', locale)}</p>
      </section>
      <section className="panel document-list">
        <div className="panel-heading"><h2>{translate('Recent documents', locale)}</h2><span>{translate('Private · workspace only', locale)}</span></div>
        {documentError && <div className="agent-error">{translate(documentError, locale)}</div>}
        {documents.map((doc) => (
          <div className="document-row" key={doc[0]}><span className="document-icon"><Files size={18} /></span><div><strong>{doc[0]}</strong><span>{doc[1]}</span></div><span className="document-status">{translate(doc[2], locale)}</span><span>{translate(doc[3], locale)}</span></div>
        ))}
        {!documents.length && !documentError && <div className="empty-list">{translate('No documents uploaded. Add evidence to begin a document review.', locale)}</div>}
      </section>
      {toast && <button className="toast" onClick={() => setToast('')}>{toast}<X size={14} /></button>}
    </>
  )
}

function Radar({ locale }: { locale: Locale }) {
  const [scanning, setScanning] = useState(false)
  const [updates, setUpdates] = useState<any[]>([])
  const [radarError, setRadarError] = useState('')
  useEffect(() => {
    api<{updates?:any[]}>('/api/v1/regulatory/updates')
      .then((data) => setUpdates(data.updates || []))
      .catch((error) => setRadarError(error instanceof Error ? error.message : 'Could not load source records'))
  }, [])
  const scan = async () => {
    setScanning(true)
    setRadarError('')
    try {
      await api('/api/v1/regulatory/scans', { method: 'POST' })
      const latest = await api<{updates?:any[]}>('/api/v1/regulatory/updates')
      setUpdates(latest.updates || [])
    } catch (error) {
      setRadarError(error instanceof Error ? error.message : 'Source scan failed')
    } finally {
      setScanning(false)
    }
  }
  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">{translate('REGULATORY OBSERVATORY', locale)}</p><h1>{translate('Impact Radar', locale)}</h1></div><button className="secondary-button" onClick={() => void scan()} disabled={scanning}><RadarIcon size={16} /> {translate(scanning ? 'Scanning sources...' : 'Run source scan', locale)}</button></div>
      {radarError && <div className="agent-error">{translate(radarError, locale)}</div>}
      <section className="radar-grid">
        <article className="panel radar-timeline"><div className="panel-heading"><h2>{translate('Captured source records', locale)}</h2><span>{updates.length} {translate('records', locale)}</span></div>
          {updates.length ? updates.map((update) => <div className="timeline-row" key={update.id}><span>{translate('RECENT', locale)}</span><div className="timeline-line"><i className="amber" /></div><div><strong>{update.title}</strong><span className="status-badge amber">{translate(update.review_state, locale)}</span></div></div>) : <div className="empty-list">{translate('No source updates have been recorded. Run a source scan to capture current official pages.', locale)}</div>}
        </article>
        <article className="panel radar-impact"><p className="eyebrow">{translate('SOURCE RECORD', locale)}</p><h2>{updates[0]?.authority || translate('No captured source yet', locale)}</h2><div className="impact-score"><span>{updates[0] ? '01' : '—'}</span><div><strong>{updates[0]?.title || translate('Run a source scan to capture an official page.', locale)}</strong><p>{updates[0]?.jurisdiction || translate('West Bengal', locale)}</p><p>{updates[0]?.review_state ? `${translate('Review state:', locale)} ${translate(updates[0].review_state, locale)}. ${translate('Capture is not legal verification.', locale)}` : translate('No source record is available.', locale)}</p></div></div>{updates[0]?.url ? <a className="primary-button" href={updates[0].url} target="_blank" rel="noreferrer">{translate('Open captured source', locale)} <ArrowRight size={16} /></a> : <button className="primary-button" disabled>{translate('Source URL unavailable', locale)}</button>}</article>
      </section>
    </>
  )
}

function Simulator({ locale }: { locale: Locale }) {
  const [employees, setEmployees] = useState(2)
  const [online, setOnline] = useState(true)
  const [saved, setSaved] = useState(false)
  const [profile, setProfile] = useState<any>(null)
  const [scenario, setScenario] = useState<any>(null)
  const [scenarioError, setScenarioError] = useState('')
  useEffect(() => {
    let active = true
    const loadProfile = async () => {
      try {
        const businessId = await getActiveBusinessId()
        if (!businessId) return
        const data = await api<{items?:any[]}>(`/api/v1/businesses/${encodeURIComponent(businessId)}/profile-history`)
        if (active) setProfile(data.items?.[0]?.facts || null)
      } catch (error) {
        if (active) setScenarioError(error instanceof Error ? error.message : 'Could not load the current profile')
      }
    }
    void loadProfile()
    return () => { active = false }
  }, [])
  const isFood = profile
    ? profile.activities?.some((activity: string) => /food|baking|cooking|catering/i.test(activity)) || /food|bakery/i.test(profile.business_type || '')
    : null
  const saveScenario = async () => {
    setScenarioError('')
    try {
      const businessId = await getActiveBusinessId()
      const scope = businessId
        ? `business_id=${encodeURIComponent(businessId)}`
        : `workspace_id=${encodeURIComponent(getWorkspaceId())}`
      const result = await api<any>(`/api/v1/simulations?${scope}&employee_count=${employees}&sell_online=${online}`, { method: 'POST' })
      setScenario(result)
      setSaved(true)
    } catch (error) {
      setScenarioError(error instanceof Error ? error.message : 'Could not evaluate this scenario')
    }
  }
  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">{translate('WHAT-IF LAB', locale)}</p><h1>{translate('Compare outcomes', locale)}</h1></div><button className="primary-button" onClick={saveScenario}>{translate(saved ? 'Scenario saved' : 'Save scenario', locale)} <ArrowRight size={16} /></button></div>
      <section className="simulator-layout">
        <aside className="panel simulator-controls"><p className="eyebrow">{translate('HYPOTHETICAL CHANGES', locale)}</p><h2>{translate('Adjust the profile', locale)}</h2>
          <label>{translate('Employee count', locale)} <strong>{employees}</strong></label><input type="range" min="1" max="10" value={employees} onChange={(e) => setEmployees(Number(e.target.value))} />
          <label className="toggle-row"><span>{translate('Sell online', locale)}</span><button className={online ? 'toggle on' : 'toggle'} onClick={() => setOnline(!online)}><i /></button></label>
          <div className="scenario-note"><ShieldCheck size={16} /><p>{translate('This scenario does not alter the live business profile.', locale)}</p></div>
        </aside>
        <article className="panel comparison">
          <div className="comparison-head"><p className="eyebrow">{translate('BASELINE → SCENARIO', locale)}</p><h2>{scenario ? `${scenario.scenario_requirements} ${translate('candidate checks', locale)}` : translate('Run a scenario to compare', locale)}</h2></div>
          {scenarioError && <div className="agent-error">{translate(scenarioError, locale)}</div>}
          <div className="comparison-grid">
            <div><p>{translate('BASELINE', locale)}</p><strong>{scenario?.baseline_requirements ?? '—'}</strong><span>{translate('candidate checks', locale)}</span></div><ArrowRight size={20} /><div><p>{translate('SCENARIO', locale)}</p><strong>{scenario?.scenario_requirements ?? '—'}</strong><span>{translate('candidate checks', locale)}</span></div>
          </div>
          {isFood === null
            ? <div className="change-card"><span className="change-icon minus">i</span><div><strong>{translate('No confirmed business profile', locale)}</strong><p>{translate('Candidate checks are not assumed until you add a business profile.', locale)}</p></div></div>
            : <div className="change-card"><span className="change-icon plus">i</span><div><strong>{translate(isFood ? 'Food-related checks included as candidates' : 'No food-specific checks for this profile', locale)}</strong><p>{translate('Food-sector checks are included only when the confirmed profile indicates food activity.', locale)}</p></div></div>}
          {scenario?.changes?.length
            ? scenario.changes.map((change: any) => <div className="change-card" key={change.rule_id}><span className={`change-icon ${change.type === 'ADDED' ? 'plus' : 'minus'}`}>{change.type === 'ADDED' ? '+' : '−'}</span><div><strong>{change.rule_id}: {translate(change.type, locale)}</strong><p>{translate(change.before || 'No baseline result', locale)} → {translate(change.after || 'No scenario result', locale)}</p></div></div>)
            : <div className="change-card"><span className="change-icon minus">i</span><div><strong>{translate('Rule changes not evaluated', locale)}</strong><p>{translate('Results are candidate checks and must be verified with official sources.', locale)}</p></div></div>}
          <p className="agent-disclaimer">{translate(scenario?.disclaimer || 'Run the scenario to calculate profile-based candidate checks. This is not a legal determination.', locale)}</p>
        </article>
      </section>
    </>
  )
}

type CandidateForm = {
  title: string
  official_url: string
  source_page?: string
  status?: string
  validation_status?: string
  checked_on?: string
  http_status?: number | null
  resource_type?: string
  resolved_url?: string
  page_title?: string
  page_excerpt?: string
  document_type?: string
  byte_size?: number
  page_count?: number | null
  preview_status?: string
  text_excerpt?: string
  preview_url?: string
  content_hash?: string
  fillable_fields?: Array<{name: string; label: string; type: string}>
  suggested_values?: Record<string, string>
  capture_error?: string
}

function CandidateForms({ forms, sessionId, locale }: { forms: CandidateForm[]; sessionId: string; locale: Locale }) {
  const [fieldValues, setFieldValues] = useState<Record<string, Record<string, string>>>({})
  const [fillError, setFillError] = useState('')
  const [fillMessage, setFillMessage] = useState('')
  const [fillingHash, setFillingHash] = useState('')

  const fillForm = async (form: CandidateForm) => {
    if (!form.content_hash) return
    setFillingHash(form.content_hash)
    setFillError('')
    setFillMessage('')
    try {
      await downloadPostFile(
        `/api/v1/agent/sessions/${encodeURIComponent(sessionId)}/forms/${encodeURIComponent(form.content_hash)}/fill`,
        'permitpilot-filled-draft.pdf',
        { fields: { ...(form.suggested_values || {}), ...(fieldValues[form.content_hash] || {}) } },
      )
      setFillMessage(locale === 'hi'
        ? `“${form.title}” का भरा हुआ मसौदा डाउनलोड हुआ। उपयोग से पहले हर मान जाँचें।`
        : `A filled draft of “${form.title}” was downloaded. Check every value before using it.`)
    } catch (error) {
      setFillError(error instanceof Error ? error.message : 'The filled draft could not be created')
    } finally {
      setFillingHash('')
    }
  }

  if (!forms.length) return null
  return (
    <div className="candidate-form-links">
      <strong>{translate('Official links — live reachability checked', locale)}</strong>
      <p className="agent-disclaimer">{translate('A responding portal page is not a blank form. Downloaded PDFs appear below; 404/410 links are marked not found and cannot be opened from this list.', locale)}</p>
      {fillError && <p className="agent-error">{translate(fillError, locale)}</p>}
      {fillMessage && <p className="form-fill-message" role="status">{fillMessage}</p>}
      {forms.map((form) => (
        <article className={`candidate-form-card ${form.validation_status === 'not_found' ? 'candidate-form-card--invalid' : ''}`} key={form.official_url}>
          <div className="candidate-form-card__heading">
            <strong>{form.title}</strong>
            <span className={`candidate-form-status candidate-form-status--${form.validation_status || 'unverified'}`}>
              {form.validation_status === 'not_found'
                ? `${translate('NOT FOUND', locale)}${form.http_status ? ` · HTTP ${form.http_status}` : ''}`
                : form.validation_status === 'working'
                  ? form.status === 'document_available' ? translate('PDF DOWNLOADED', locale) : translate('PORTAL RESPONDS', locale)
                  : form.validation_status === 'unreachable' ? translate('UNREACHABLE', locale) : translate('NOT VERIFIED', locale)}
            </span>
          </div>
          {form.validation_status !== 'not_found'
            ? <a href={form.resolved_url || form.official_url} target="_blank" rel="noreferrer">
                {translate(form.document_type === 'PDF' ? 'Open original official PDF' : form.status === 'portal_available' ? 'Open responding official portal page' : 'Try official link in browser', locale)} <ArrowRight size={13} />
              </a>
            : <small className="candidate-form-invalid-note">{locale === 'hi' ? `यह लिंक HTTP ${form.http_status} के साथ नहीं मिला। इसे काम करने वाला फ़ॉर्म न मानें:` : `This candidate returned HTTP ${form.http_status}. Do not use it as a working form link:`} {form.official_url}</small>}
          {form.byte_size && <small>{locale === 'hi' ? 'पूर्वावलोकन के लिए प्राप्त' : 'Retrieved for preview'} · {Math.ceil(form.byte_size / 1024)} KB</small>}
          {form.preview_url && (
            <div className="candidate-form-preview">
              <strong>{translate('Downloaded official PDF', locale)} · {form.page_count || '?'} {translate('pages', locale)}</strong>
              <iframe src={`${API_BASE}${form.preview_url}`} title={`${translate('Preview:', locale)} ${form.title}`} loading="lazy" />
            </div>
          )}
          {form.text_excerpt && (
            <details>
              <summary>{translate('View extracted text from the official PDF', locale)}</summary>
              <pre>{form.text_excerpt}</pre>
            </details>
          )}
          {form.page_excerpt && (
            <details>
              <summary>{translate('Preview text from the responding portal page', locale)}</summary>
              <pre>{form.page_excerpt}</pre>
            </details>
          )}
          {form.fillable_fields?.length ? (
            <details className="candidate-form-autofill">
              <summary>{translate('Review and prefill', locale)} {form.fillable_fields.length} PDF {locale === 'hi' ? 'पाठ फ़ील्ड' : 'text fields'}</summary>
              <p>{translate('Suggested values use confirmed business facts only. Edit or leave fields blank; this creates a local draft and never submits it.', locale)}</p>
              {form.fillable_fields.map((field) => (
                <label key={field.name}>{field.label}
                  <input
                    value={fieldValues[form.content_hash || '']?.[field.name] ?? form.suggested_values?.[field.name] ?? ''}
                    onChange={(event) => {
                      const hash = form.content_hash || ''
                      setFieldValues((current) => ({
                        ...current,
                        [hash]: { ...(current[hash] || {}), [field.name]: event.target.value },
                      }))
                    }}
                  />
                </label>
              ))}
              <button
                className="secondary-button"
                onClick={() => void fillForm(form)}
                disabled={fillingHash === form.content_hash || !Object.values({ ...(form.suggested_values || {}), ...(fieldValues[form.content_hash || ''] || {}) }).some((value) => value.trim())}
              >
                {translate(fillingHash === form.content_hash ? 'Creating draft...' : 'Download filled draft', locale)}
              </button>
            </details>
          ) : form.document_type === 'PDF' && form.status === 'document_available' && (
            <small>{translate('This PDF is viewable, but it has no detected fillable text fields. Use the original form manually.', locale)}</small>
          )}
          {form.preview_status === 'no_selectable_text' && <small>{locale === 'hi' ? 'इस फ़ाइल में चुना जा सकने वाला पाठ नहीं है; यह स्कैन किया हुआ फ़ॉर्म हो सकता है। मूल दस्तावेज़ देखें।' : 'This file has no selectable text; it may be a scanned form. Open the original document to inspect it.'}</small>}
          {form.preview_status === 'unreadable' && <small>{locale === 'hi' ? 'फ़ाइल मिली, लेकिन पाठ पढ़ा नहीं जा सका। मूल दस्तावेज़ देखें।' : 'The file was retrieved, but its text could not be decoded. Open the original document to inspect it.'}</small>}
          {form.capture_error && <small>{locale === 'hi' ? 'सीधा डाउनलोड विफल:' : 'Direct retrieval failed:'} {form.capture_error} {locale === 'hi' ? 'आधिकारिक लिंक फिर भी आज़मा सकते हैं।' : 'The official link is still available.'}</small>}
          {form.status === 'fetch_limit_reached' && <small>{locale === 'hi' ? 'जाँच की सीमा पूरी हुई; यह लिंक अपुष्ट है और इसे काम करने वाला फ़ॉर्म नहीं दिखाया गया है।' : 'Reachability check limit reached; this link is unverified and is not shown as a working form.'}</small>}
          {form.checked_on && <small>{locale === 'hi' ? 'जाँच की तारीख' : 'Checked on'} {form.checked_on} · {form.resource_type === 'portal_page' ? locale === 'hi' ? 'पोर्टल पेज, डाउनलोड किया हुआ फ़ॉर्म नहीं' : 'Portal page, not a downloaded form' : locale === 'hi' ? 'स्रोत से मिला दस्तावेज़' : 'Source-discovered document'}</small>}
        </article>
      ))}
      <p className="agent-disclaimer">{translate('Source-discovered resources are not proof that a form applies to your business. Verify the form and all details with the authority before signing or submitting.', locale)}</p>
    </div>
  )
}

function AgentNavigator({ locale }: { locale: Locale }) {
  const [goal, setGoal] = useState('')
  const [session, setSession] = useState<any>(null)
  const [answer, setAnswer] = useState('')
  const [research, setResearch] = useState<any>(null)
  const [review, setReview] = useState<any>(null)
  const [reviewerName, setReviewerName] = useState('')
  const [reviewAcknowledged, setReviewAcknowledged] = useState(false)
  const [agentError, setAgentError] = useState('')
  const [agentLoading, setAgentLoading] = useState(false)

  const startAgent = async () => {
    setAgentLoading(true)
    setAgentError('')
    setSession(null)
    setAnswer('')
    setResearch(null)
    setReview(null)
    setReviewerName('')
    setReviewAcknowledged(false)
    try {
      const data = await api<any>(`/api/v1/agent/sessions?workspace_id=${encodeURIComponent(getWorkspaceId())}&goal=${encodeURIComponent(goal)}`, { method: 'POST' })
      setSession(data)
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : 'Could not start the agent')
    } finally {
      setAgentLoading(false)
    }
  }

  const sendAnswer = async () => {
    if (!session || !answer.trim()) return
    setAgentLoading(true)
    setAgentError('')
    try {
      const data = await api<any>(`/api/v1/agent/sessions/${session.session_id}/message`, {
        method: 'POST',
        body: JSON.stringify({ message: answer }),
      })
      setSession(data)
      setAnswer('')
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : 'Could not process your answer')
    } finally {
      setAgentLoading(false)
    }
  }

  const discoverSources = async () => {
    if (!session) return
    setAgentLoading(true)
    setAgentError('')
    try {
      const data = await api<any>(`/api/v1/agent/sessions/${session.session_id}/research`, { method: 'POST' })
      setResearch(data)
      setSession((current: any) => current ? { ...current, stage: data.status === 'unsupported_jurisdiction' ? 'out_of_scope' : 'research_complete' } : current)
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : 'Official-source discovery failed')
    } finally {
      setAgentLoading(false)
    }
  }

  const generatePackage = async () => {
    if (!session) return
    setAgentLoading(true)
    setAgentError('')
    try {
      const data = await api<any>(`/api/v1/agent/sessions/${session.session_id}/generate`, { method: 'POST' })
      setReview(data.review)
      setSession((current: any) => current ? { ...current, stage: 'review' } : current)
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : 'PDF review package could not be generated')
    } finally {
      setAgentLoading(false)
    }
  }

  const approvePackage = async () => {
    if (!session || !reviewerName.trim()) return
    setAgentLoading(true)
    setAgentError('')
    try {
      await api(`/api/v1/agent/sessions/${session.session_id}/approve?reviewer_name=${encodeURIComponent(reviewerName)}`, { method: 'POST' })
      setReviewAcknowledged(true)
      setSession((current: any) => current ? { ...current, stage: 'approved' } : current)
    } catch (error) {
      setAgentError(error instanceof Error ? error.message : 'Could not record the review')
    } finally {
      setAgentLoading(false)
    }
  }

  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">{translate('RESEARCH + HUMAN REVIEW · WEST BENGAL', locale)}</p><h1>{translate('Red Tape Navigator', locale)}</h1></div><span className="agent-status"><Bot size={15} /> {translate('Local workflow', locale)}</span></div>
      <section className="agent-layout">
        <aside className="panel agent-goal">
          <p className="eyebrow">{translate('OBJECTIVE', locale)}</p>
          <h2>{translate('What do you want to accomplish?', locale)}</h2>
          <textarea value={goal} onChange={(event) => setGoal(event.target.value)} placeholder={translate('e.g. I want to open a retail shop in Kolkata', locale)} />
          <button className="primary-button" onClick={startAgent} disabled={!goal.trim() || agentLoading}><Bot size={16} /> {agentLoading ? translate('Working...', locale) : translate('Start navigator', locale)}</button>
          {session && <div className="agent-progress"><span>{translate('01 Interview', locale)}</span><span className={research ? 'done' : ''}>{translate('02 Research', locale)}</span><span className={review ? 'done' : ''}>{translate('03 Review sheet', locale)}</span><span className={reviewAcknowledged ? 'done' : ''}>{translate('04 Acknowledgment', locale)}</span></div>}
          <p className="agent-disclaimer">{translate('Research coverage is limited to West Bengal. Findings and links are leads for human verification, not legal advice.', locale)}</p>
        </aside>
        <article className="panel agent-chat">
          <div className="agent-chat-header"><div><Bot size={18} /><strong>{translate('PermitPilot Agent', locale)}</strong></div><span>{translate(session?.stage || 'Awaiting objective', locale)}</span></div>
          <div className="agent-messages">
            {!session && <div className="agent-empty"><ShieldCheck size={24} /><strong>{translate('Define a goal to begin', locale)}</strong><p>{translate('The agent will prefill known facts, ask about missing preparation details, and search sources that match the business activity.', locale)}</p></div>}
            {agentError && <div className="agent-error">{translate(agentError, locale)}</div>}
            {session?.messages?.map((message: any, index: number) => (
              <div className={`agent-message ${message.role}`} key={index}><span>{message.role === 'agent' ? 'PP' : locale === 'hi' ? 'आप' : 'YOU'}</span><p>{message.content}</p></div>
            ))}
          </div>
          {session && !['ready_to_research', 'research_complete', 'out_of_scope', 'review', 'approved'].includes(session.stage) && (
            <div className="agent-input"><input value={answer} onChange={(event) => setAnswer(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && sendAnswer()} placeholder={translate('Answer the agent...', locale)} /><button onClick={sendAnswer} aria-label={locale === 'hi' ? 'जवाब भेजें' : 'Send answer'} disabled={agentLoading}><Send size={16} /></button></div>
          )}
          {session && session.stage === 'ready_to_research' && !research && (
            <button className="primary-button agent-action" onClick={discoverSources}><Search size={16} /> {translate('Find sources & candidate form links', locale)}</button>
          )}
          {research && !review && (
            <div className="source-results">
          <p className="eyebrow">{translate('LIVE OFFICIAL-SITE EXTRACTION · REVIEW REQUIRED', locale)}</p>
          <p className="agent-disclaimer">
            {locale === 'hi'
          ? `${research.sources?.filter((source: any) => source.captured).length || 0} सार्वजनिक पेज प्राप्त हुए। टूल अस्थायी टाइमआउट पर एक बार फिर कोशिश करता है, उसी अनुमति-प्राप्त होस्ट के अधिकतम दो संबंधित लिंक देखता है और अधिकतम चार PDF का पूर्वावलोकन करता है। TLS सुरक्षा नहीं हटाई जाती; JavaScript या लॉगिन वाले पोर्टल उपलब्ध न हों।`
          : `Extracted ${research.sources?.filter((source: any) => source.captured).length || 0} public pages. The reader retries transient timeouts once, follows at most two relevant links on the same allowlisted host, and previews up to four linked PDF forms. It never bypasses TLS checks; JavaScript-only or login-protected portals may still be unavailable.`}
          </p>
              {research.status === 'unsupported_jurisdiction' && <div className="agent-error">{translate(research.warnings[0], locale)} {translate('Start a new goal that specifies a West Bengal location.', locale)}</div>}
              {research.source_summaries?.length > 0 && (
                <div className="source-summaries">
                  <strong>{translate('AI notes from captured public text — verify every quote', locale)}</strong>
                  {research.source_summaries.map((summary: any) => (
                    <div key={summary.source_url}>
                      <a href={summary.source_url} target="_blank" rel="noreferrer">{translate('Open cited source', locale)}</a>
                      {summary.findings.map((finding: any, index: number) => (
                        <blockquote key={index}><p>{finding.statement}</p><small>{translate('Evidence:', locale)} {finding.evidence_quote}</small></blockquote>
                      ))}
                    </div>
                  ))}
                </div>
              )}
              {research.live_search?.status === 'available' && (
                <div className="source-summaries">
                  <strong>{translate('Gemini real-time web search — research lead, not verified legal guidance', locale)}</strong>
                  <p>{research.live_search.answer}</p>
                  {research.live_search.sources.map((source: any) => source.validation_status === 'not_found'
                    ? <p className="candidate-form-invalid-note" key={source.url}>{source.title}: {translate('NOT FOUND', locale)} · HTTP {source.http_status || '404/410'} · {source.url}</p>
                    : <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>{source.title}: {translate(source.validation_status === 'working' ? 'verified responding citation' : 'unverified citation', locale)} ↗</a>)}
                </div>
              )}
              {research.status !== 'unsupported_jurisdiction' && <button className="secondary-button" onClick={discoverSources} disabled={agentLoading}>{agentLoading ? translate('Checking portals...', locale) : translate('Refresh official portal pages', locale)}</button>}
              {(research.sources || []).map((source: any) => (
                <div className={`source-result ${source.validation_status === 'not_found' ? 'source-result--invalid' : ''}`} key={source.url}>
                  {source.validation_status === 'not_found'
                    ? <div className="source-result__invalid"><strong>{source.authority} · {translate('NOT FOUND', locale)} · HTTP {source.http_status}</strong><span>{source.title} · {locale === 'hi' ? 'जाँच' : 'Checked'} {source.checked_on}</span><small>{source.url}</small></div>
                    : <a href={source.url} target="_blank" rel="noreferrer"><strong>{source.authority} · {translate(source.page_depth === 1 ? 'LINKED PAGE' : 'START PAGE', locale)} · {translate(source.captured ? 'RESPONDING' : 'UNVERIFIED', locale)}</strong><span>{source.captured ? source.title : translate(source.capture_error, locale)}</span><ArrowRight size={14} /></a>}
                  {source.captured && <details><summary>{translate('Extracted text (not legal interpretation)', locale)}</summary>{source.highlights?.length ? source.highlights.map((highlight: string, index: number) => <p key={index}>{highlight}</p>) : <p>{translate('No registration or application-related text was extracted.', locale)}</p>}<small>{translate('Source:', locale)} {source.url} · SHA-256: {source.content_hash}</small></details>}
                </div>
              ))}
              {research.forms?.length > 0
                ? <CandidateForms forms={research.forms} sessionId={session.session_id} locale={locale} />
                : research.status !== 'unsupported_jurisdiction' && <p>{translate('No form document or application link was found in the captured pages. No official form has been mapped or filled.', locale)}</p>}
              {(research.warnings || []).filter((warning: string) => !warning.includes('West Bengal, India')).map((warning: string) => <p className="agent-disclaimer" key={warning}>{translate(warning, locale)}</p>)}
              {research.status !== 'unsupported_jurisdiction' && <button className="primary-button" onClick={generatePackage} disabled={agentLoading}>{agentLoading ? translate('Preparing...', locale) : translate('Generate fact sheet for review', locale)}</button>}
            </div>
          )}
        </article>
        {review && (
          <aside className="panel agent-review">
            <p className="eyebrow">{translate('HUMAN REVIEW CHECKPOINT', locale)}</p>
            <h2>{translate(review.form_title, locale)}</h2>
            <p className="agent-disclaimer">{translate(review.disclaimer, locale)}</p>
            <div className="review-fields">{review.mapped_fields.map(([label, value]: [string, any]) => <div key={label}><span>{translate(label, locale)}</span><strong>{value ?? translate('NOT PROVIDED', locale)}</strong></div>)}</div>
            {review.missing?.length > 0 && <p>{translate('Not confirmed:', locale)} {review.missing.map((item: string) => translate(item, locale)).join(', ')}</p>}
            {review.unconfirmed?.length > 0 && <p>{translate('Parsed from goal; confirm before use:', locale)} {review.unconfirmed.map((item: string) => translate(item, locale)).join(', ')}</p>}
            {review.source_summaries?.length > 0 && (
              <div className="source-summaries">
                <strong>{translate('AI notes from captured public text — verify every quote', locale)}</strong>
                {review.source_summaries.map((summary: any) => (
                  <div key={summary.source_url}>
                    <a href={summary.source_url} target="_blank" rel="noreferrer">{translate('Open cited source', locale)}</a>
                    {summary.findings.map((finding: any, index: number) => (
                      <blockquote key={index}><p>{finding.statement}</p><small>{translate('Evidence:', locale)} {finding.evidence_quote}</small></blockquote>
                    ))}
                  </div>
                ))}
              </div>
            )}
            {review.live_search?.status === 'available' && (
              <div className="source-summaries">
                <strong>{translate('Gemini real-time web search — verify the cited government pages', locale)}</strong>
                <p>{review.live_search.answer}</p>
                {review.live_search.sources.map((source: any) => (
                  <a href={source.url} target="_blank" rel="noreferrer" key={source.url}>{source.title}: {translate('open official citation', locale)}</a>
                ))}
              </div>
            )}
            {review.sources?.length > 0 && (
              <div className="candidate-form-links">
                <strong>{translate('Official portal pages', locale)}</strong>
                {review.sources.map((source: any) => (
                  <div className="source-result" key={source.url}>
                    {source.validation_status === 'not_found'
                      ? <div className="source-result__invalid"><strong>{source.authority} · {translate('NOT FOUND', locale)} · HTTP {source.http_status}</strong><span>{source.title}</span><small>{source.url}</small></div>
                      : <a href={source.url} target="_blank" rel="noreferrer">
                          <strong>{source.authority} · {translate(source.page_depth === 1 ? 'LINKED PAGE' : 'START PAGE', locale)} · {translate(source.captured ? 'RESPONDING' : 'UNVERIFIED', locale)}</strong>
                          <span>{source.captured ? source.title : translate('Try official portal directly (capture failed)', locale)}</span>
                        </a>}
                    {source.captured && source.highlights?.length > 0 && (
                      <details><summary>{translate('Extracted source text', locale)}</summary>{source.highlights.map((highlight: string, index: number) => <p key={index}>{highlight}</p>)}</details>
                    )}
                  </div>
                ))}
              </div>
            )}
            {review.candidate_forms?.length
              ? <CandidateForms forms={review.candidate_forms} sessionId={session.session_id} locale={locale} />
              : <p>{translate('No official application form was found or filled.', locale)}</p>}
            <button className="secondary-button" onClick={async () => { try { await downloadFile(review.pdf_url, 'permitpilot-preparation-sheet.pdf') } catch (error) { setAgentError(error instanceof Error ? error.message : 'Could not download the review sheet') } }}><FileText size={15} /> {translate('Download preparation sheet', locale)}</button>
            {!reviewAcknowledged ? (
              <div className="signature-box"><label>{translate('Reviewer name (acknowledgment only)', locale)}<input value={reviewerName} onChange={(event) => setReviewerName(event.target.value)} placeholder={locale === 'hi' ? 'नाम' : 'Name'} /></label><button className="primary-button" onClick={approvePackage} disabled={!reviewerName.trim() || agentLoading}><Check size={15} /> {translate('Record review', locale)}</button></div>
            ) : (
              <div className="approval-success"><Check size={16} /><strong>{translate('Review acknowledgment recorded', locale)}</strong><span>{locale === 'hi' ? 'यह हस्ताक्षर नहीं है। स्वयं आधिकारिक प्राधिकरण से पुष्टि करें, हस्ताक्षर करें और जमा करें।' : 'This is not a signature. Verify, sign, and submit through the official authority yourself.'}</span></div>
            )}
          </aside>
        )}
      </section>
    </>
  )
}

function TasksPage({ locale }: { locale: Locale }) {
  const [tasks, setTasks] = useState<Array<{id:string,title:string,status:string,priority:string,due_date:string|null}>>([])
  const [taskError, setTaskError] = useState('')
  const [completingTask, setCompletingTask] = useState<string | null>(null)
  useEffect(() => {
    api<{items:any[]}>(`/api/v1/tasks?workspace_id=${encodeURIComponent(getWorkspaceId())}`).then((data) => setTasks(data.items)).catch((error) => setTaskError(error instanceof Error ? error.message : 'Could not load tasks'))
  }, [])
  const completeTask = async (taskId: string) => {
    setTaskError('')
    setCompletingTask(taskId)
    try {
      await api(`/api/v1/tasks/${encodeURIComponent(taskId)}?status=done`, { method: 'PATCH' })
      setTasks((current) => current.map((task) => task.id === taskId ? {...task, status: 'done'} : task))
    } catch (error) {
      setTaskError(error instanceof Error ? error.message : 'Could not update task')
    } finally {
      setCompletingTask(null)
    }
  }
  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">{translate('ACTION CENTRE', locale)}</p><h1>{translate('Tasks', locale)}</h1></div><button className="primary-button" onClick={async () => { const title=window.prompt(translate('Task title', locale)); if(!title) return; try { const task=await api<any>(`/api/v1/tasks?workspace_id=${encodeURIComponent(getWorkspaceId())}&title=${encodeURIComponent(title)}&priority=medium`, {method:'POST'}); setTasks((current)=>[...current,task]) } catch(error){setTaskError(error instanceof Error ? error.message : 'Could not add task')} }}>{translate('Add task', locale)}</button></div>
      <section className="panel task-list">
        {taskError && <div className="agent-error">{translate(taskError, locale)}</div>}
        {tasks.map((task) => (
          <div className="task-row" key={task.id}>
            <button className={task.status === 'done' ? 'task-check checked' : 'task-check'} onClick={() => void completeTask(task.id)} disabled={task.status === 'done' || completingTask === task.id} aria-label={translate('Mark task complete', locale)}>{task.status === 'done' && <Check size={13} />}</button>
            <div><strong>{task.title}</strong><span>{translate(task.priority, locale)} {translate('priority', locale)} · {task.due_date || translate('No deadline', locale)}</span></div>
            <span className={`status-badge ${task.status === 'done' ? 'lime' : 'amber'}`}>{translate(task.status, locale)}</span>
          </div>
        ))}
      </section>
    </>
  )
}

type MembershipPlanId = 'starter' | 'pro' | 'premium'
type PaymentPreviewMethod = 'upi' | 'card' | 'netbanking'

const membershipPlans: Array<{
  id: MembershipPlanId
  name: string
  price: string
  billing: string
  description: string
  features: string[]
  featured?: boolean
}> = [
  {
    id: 'starter',
    name: 'Starter',
    price: '₹0',
    billing: 'Free forever',
    description: 'A practical starting point for vendors and micro businesses.',
    features: ['Business setup workspace', 'Self-serve compliance discovery', 'Tasks and deadline tracking'],
  },
  {
    id: 'pro',
    name: 'Pro',
    price: '₹699',
    billing: 'Per month',
    description: 'Expert help for the filings that keep your business moving.',
    features: ['Dedicated compliance expert', 'Filing and approval assistance', 'Renewal reminders and guidance'],
  },
  {
    id: 'premium',
    name: 'Premium',
    price: '₹1,499',
    billing: 'Per month · 6-month program',
    description: 'End-to-end launch and operational handholding for six months.',
    features: ['Full six-month business launch support', 'Legal Shield guidance and issue triage', 'Loan-readiness and application assistance'],
    featured: true,
  },
]

function MembershipPage({ locale }: { locale: Locale }) {
  const [savedPlan, setSavedPlan] = useState<MembershipPlanId | null>(() => {
    const stored = localStorage.getItem('permitpilot-plan-preview')
    return stored === 'starter' || stored === 'pro' || stored === 'premium' ? stored : null
  })
  const [checkoutPlan, setCheckoutPlan] = useState<Exclude<MembershipPlanId, 'starter'> | null>(null)
  const [paymentMethod, setPaymentMethod] = useState<PaymentPreviewMethod>('upi')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const selectedPlan = membershipPlans.find((plan) => plan.id === checkoutPlan)

  const savePlanPreview = (planId: MembershipPlanId) => {
    setError('')
    try {
      localStorage.setItem('permitpilot-plan-preview', planId)
      setSavedPlan(planId)
      setCheckoutPlan(null)
      const planName = membershipPlans.find((plan) => plan.id === planId)?.name || 'plan'
      setNotice(locale === 'hi'
        ? `आपका ${translate(planName, locale)} प्लान इस ब्राउज़र में सहेजा गया। कोई भुगतान नहीं हुआ।`
        : `Your ${planName} plan selection is saved in this browser. No payment was taken.`)
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not save your plan selection')
    }
  }

  return (
    <>
      <div className="page-heading membership-heading">
        <div><p className="eyebrow">{translate('MEMBERSHIP / BUSINESS SUPPORT', locale)}</p><h1>{translate('Choose your next move.', locale)}</h1></div>
        <span className="membership-demo-tag">{translate('FRONTEND PREVIEW · NO CHARGE', locale)}</span>
      </div>
      <section className="membership-intro panel">
        <div>
          <p className="eyebrow">{translate('BUILT FOR NEW VENDORS & MICRO BUSINESSES', locale)}</p>
          <h2>{translate('Start free. Add a human when you need one.', locale)}</h2>
          <p>{translate('Pick self-serve tools, focused compliance help, or a six-month guided launch. Choose a plan to preview the checkout flow.', locale)}</p>
        </div>
        <div className="membership-stamp"><CreditCard size={22} /><span>{translate('3 LEVELS', locale)}<br />{translate('ONE LAUNCHPAD', locale)}</span></div>
      </section>
      {(notice || error) && <div className={error ? 'agent-error' : 'membership-notice'} role={error ? 'alert' : 'status'}>{translate(error || notice, locale)}</div>}
      <section className="plan-grid" aria-label={translate('Membership plans', locale)}>
        {membershipPlans.map((plan, index) => (
          <article className={`plan-card ${plan.featured ? 'featured' : ''} ${savedPlan === plan.id ? 'selected' : ''}`} key={plan.id}>
            <div className="plan-card-top">
              <span className="plan-index">0{index + 1} / {translate('PLAN', locale)}</span>
              {plan.featured && <span className="plan-ribbon">{translate('6-MONTH LAUNCH', locale)}</span>}
            </div>
            <h2>{translate(plan.name, locale)}</h2>
            <p className="plan-description">{translate(plan.description, locale)}</p>
            <div className="plan-price"><strong>{plan.price}</strong><span> / {translate('month', locale)}</span></div>
            <p className="plan-billing">{translate(plan.billing, locale)}</p>
            {plan.id === 'premium' && <p className="plan-total">{translate('6-month program total:', locale)} <strong>₹8,994</strong></p>}
            <div className="plan-divider" />
            <ul className="plan-features">
              {plan.features.map((feature) => <li key={feature}><Check size={15} /><span>{translate(feature, locale)}</span></li>)}
            </ul>
            <button
              className={plan.featured ? 'primary-button plan-action' : 'secondary-button plan-action'}
              aria-pressed={savedPlan === plan.id}
              onClick={() => {
                setNotice('')
                setError('')
                if (plan.id === 'starter') savePlanPreview('starter')
                else {
                  setCheckoutPlan(plan.id)
                  setPaymentMethod('upi')
                }
              }}
            >
              {savedPlan === plan.id ? translate('Selected in demo', locale) : plan.id === 'starter' ? translate('Choose Starter', locale) : `${translate('Continue with', locale)} ${translate(plan.name, locale)}`}
              <ArrowRight size={15} />
            </button>
          </article>
        ))}
      </section>
      {selectedPlan && (
        <section className="checkout-preview panel" aria-live="polite">
          <div className="checkout-copy">
            <p className="eyebrow">{translate('CHECKOUT PREVIEW', locale)} / {translate(selectedPlan.name, locale).toUpperCase()}</p>
            <h2>{translate('Review your plan', locale)}</h2>
            <p>{translate(selectedPlan.id === 'premium'
              ? 'Six-month launch program · ₹1,499 per month · ₹8,994 total for six months.'
              : 'Monthly membership · ₹699 per month.', locale)}</p>
            <p className="agent-disclaimer">{translate('Payment providers are not connected. Do not enter payment details here; this preview will not charge you or activate a real service.', locale)}</p>
          </div>
          <div className="checkout-controls">
            <span className="checkout-label">{translate('PAYMENT METHOD PREVIEW', locale)}</span>
            <div className="payment-methods" role="group" aria-label={translate('Choose a payment method preview', locale)}>
              {([
                ['upi', 'UPI'],
                ['card', 'Card'],
                ['netbanking', 'Net banking'],
              ] as Array<[PaymentPreviewMethod, string]>).map(([method, label]) => (
                <button className={paymentMethod === method ? 'payment-method active' : 'payment-method'} key={method} aria-pressed={paymentMethod === method} onClick={() => setPaymentMethod(method)}>
                  {paymentMethod === method && <Check size={13} />}{translate(label, locale)}
                </button>
              ))}
            </div>
            <button className="primary-button" onClick={() => savePlanPreview(selectedPlan.id)}>{translate('Save demo plan selection', locale)} <ArrowRight size={15} /></button>
          </div>
        </section>
      )}
      <p className="membership-disclaimer">{translate('Plan descriptions are proposed service tiers. Expert availability, legal support, loan outcomes, filings, and approvals are not guaranteed by this prototype. “Legal Shield” means guidance and issue triage, not legal representation or insurance.', locale)}</p>
    </>
  )
}

function SettingsPage({ onWorkspaceNameChange, locale }: { onWorkspaceNameChange: (name: string) => void; locale: Locale }) {
  const [tab, setTab] = useState<'general' | 'data'>('general')
  const [notifications, setNotifications] = useState(localStorage.getItem('permitpilot-assessment-notifications') !== 'false')
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [settingsError, setSettingsError] = useState('')
  const [workspaceName, setWorkspaceName] = useState(localStorage.getItem('permitpilot-workspace-name') || 'My Workspace')
  const [jurisdiction, setJurisdiction] = useState(localStorage.getItem('permitpilot-jurisdiction') || 'West Bengal, India')

  useEffect(() => {
    let active = true
    api<{name:string;jurisdiction:string;assessment_notifications:boolean}>(
      `/api/v1/workspaces/${encodeURIComponent(getWorkspaceId())}/settings`,
    ).then((settings) => {
      if (!active) return
      setWorkspaceName(settings.name)
      setJurisdiction(settings.jurisdiction)
      setNotifications(settings.assessment_notifications)
      localStorage.setItem('permitpilot-workspace-name', settings.name)
      localStorage.setItem('permitpilot-jurisdiction', settings.jurisdiction)
      localStorage.setItem('permitpilot-assessment-notifications', String(settings.assessment_notifications))
    }).catch((error) => {
      if (active) setSettingsError(error instanceof Error ? error.message : 'Could not load settings')
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [])

  const saveSettings = async () => {
    setSaving(true)
    setSaved(false)
    setSettingsError('')
    try {
      const settings = await api<{name:string;jurisdiction:string;assessment_notifications:boolean}>(
        `/api/v1/workspaces/${encodeURIComponent(getWorkspaceId())}/settings`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            name: workspaceName,
            jurisdiction,
            assessment_notifications: notifications,
          }),
        },
      )
      setWorkspaceName(settings.name)
      setJurisdiction(settings.jurisdiction)
      setNotifications(settings.assessment_notifications)
      localStorage.setItem('permitpilot-workspace-name', settings.name)
      localStorage.setItem('permitpilot-jurisdiction', settings.jurisdiction)
      localStorage.setItem('permitpilot-assessment-notifications', String(settings.assessment_notifications))
      onWorkspaceNameChange(settings.name)
      setSaved(true)
    } catch (error) {
      setSettingsError(error instanceof Error ? error.message : 'Could not save settings')
    } finally {
      setSaving(false)
    }
  }

  const exportWorkspace = async () => {
    setExporting(true)
    setSettingsError('')
    try {
      await downloadFile(
        `/api/v1/workspaces/${encodeURIComponent(getWorkspaceId())}/export`,
        'permitpilot-workspace-export.json',
      )
    } catch (error) {
      setSettingsError(error instanceof Error ? error.message : 'Could not export workspace data')
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">{translate('WORKSPACE / ACCOUNT', locale)}</p><h1>{translate('Settings', locale)}</h1></div>{tab === 'general' && <button className="primary-button" onClick={saveSettings} disabled={loading || saving}>{translate(saving ? 'Saving...' : saved ? 'Changes saved' : 'Save changes', locale)}</button>}</div>
      {settingsError && <div className="agent-error">{translate(settingsError, locale)}</div>}
      <section className="settings-layout">
        <aside className="panel settings-nav">
          <button className={tab === 'general' ? 'active' : ''} onClick={() => setTab('general')}>{translate('General', locale)}</button>
          <button className={tab === 'data' ? 'active' : ''} onClick={() => setTab('data')}>{translate('Data & retention', locale)}</button>
        </aside>
        <div className="panel settings-main">
          {tab === 'general' ? (
            <>
              <div className="settings-section"><p className="eyebrow">{translate('WORKSPACE', locale)}</p><h2>{workspaceName}</h2><label>{translate('Workspace name', locale)}<input value={workspaceName} onChange={(event) => { setWorkspaceName(event.target.value); setSaved(false) }} /></label><label>{translate('Jurisdiction', locale)}<input value={jurisdiction} onChange={(event) => { setJurisdiction(event.target.value); setSaved(false) }} /></label><p className="agent-disclaimer">{translate('Connected public-source coverage is currently limited to selected West Bengal portals. Changing this value does not add portal integrations.', locale)}</p></div>
              <div className="settings-section"><p className="eyebrow">{translate('NOTIFICATIONS', locale)}</p><label className="toggle-row"><span>{translate('Assessment updates', locale)}</span><button type="button" aria-pressed={notifications} className={notifications ? 'toggle on' : 'toggle'} onClick={() => { setNotifications(!notifications); setSaved(false) }}><i /></button></label><p className="agent-disclaimer">{translate(PRIVATE_DEMO_MODE ? 'This preference is saved with the shared demo workspace. The prototype does not send email or push notifications.' : 'This preference is saved with the local workspace. The prototype does not send email or push notifications.', locale)}</p></div>
            </>
          ) : (
            <div className="settings-section">
              <p className="eyebrow">{translate('DATA & RETENTION', locale)}</p>
              <h2>{translate(PRIVATE_DEMO_MODE ? 'Private demo workspace data' : 'Local workspace data', locale)}</h2>
              <p>{translate(PRIVATE_DEMO_MODE ? 'Workspace data is stored on the private demo service persistent disk. Use synthetic data only.' : 'Your workspace is stored in the local SQLite database. PermitPilot does not automatically delete your records.', locale)}</p>
              <button className="primary-button" onClick={exportWorkspace} disabled={exporting}>{translate(exporting ? 'Preparing export...' : 'Export workspace data', locale)}</button>
              <p className="agent-disclaimer">{translate('The export includes profile revisions, assessments, tasks, document metadata, reports, and agent sessions. Uploaded document files are not included.', locale)}</p>
              <div className="data-preservation-note"><strong>{translate('Workspace deletion is disabled', locale)}</strong><span>{translate(PRIVATE_DEMO_MODE ? 'This private demo preserves workspace records on its hosting disk. No records will be deleted from Settings.' : 'This local prototype preserves existing user data. No records will be deleted from Settings.', locale)}</span></div>
            </div>
          )}
        </div>
      </section>
    </>
  )
}

function App() {
  const [view, setView] = useState<View>('overview')
  const [showLanding, setShowLanding] = useState(true)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [locale, setLocale] = useState<Locale>(() => localStorage.getItem('permitpilot-locale') === 'hi' ? 'hi' : 'en')
  const [workspaceReady, setWorkspaceReady] = useState(false)
  const [workspaceError, setWorkspaceError] = useState('')
  const [workspaceName, setWorkspaceName] = useState('My Workspace')
  const [workspaceAttempt, setWorkspaceAttempt] = useState(0)
  const [accessState, setAccessState] = useState<'checking' | 'locked' | 'open' | 'error'>(PRIVATE_DEMO_MODE ? 'checking' : 'open')
  const [accessError, setAccessError] = useState('')
  const [accessAttempt, setAccessAttempt] = useState(0)
  const [lockError, setLockError] = useState('')
  const changeLocale = (nextLocale: Locale) => {
    localStorage.setItem('permitpilot-locale', nextLocale)
    setLocale(nextLocale)
  }

  useEffect(() => {
    if (!PRIVATE_DEMO_MODE) return
    let active = true
    api<{authenticated:boolean}>('/api/v1/demo/session')
      .then(({ authenticated }) => {
        if (active) setAccessState(authenticated ? 'open' : 'locked')
      })
      .catch(() => {
        if (active) {
          setAccessError('Could not connect to the private demo. Try again.')
          setAccessState('error')
        }
      })
    return () => { active = false }
  }, [accessAttempt])

  useEffect(() => {
    if (!PRIVATE_DEMO_MODE) return
    const requireAccess = () => {
      setWorkspaceReady(false)
      setAccessError('')
      setAccessState('locked')
    }
    window.addEventListener(ACCESS_REQUIRED_EVENT, requireAccess)
    return () => window.removeEventListener(ACCESS_REQUIRED_EVENT, requireAccess)
  }, [])

  const unlockDemo = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setAccessError('')
    const formData = new FormData(event.currentTarget)
    try {
      await api('/api/v1/demo/login', {
        method: 'POST',
        body: JSON.stringify({ code: formData.get('demo-access-code') }),
      })
      setAccessState('open')
      setWorkspaceError('')
      setWorkspaceAttempt((attempt) => attempt + 1)
    } catch (error) {
      setAccessError(error instanceof Error ? error.message : 'Invalid demo access code')
    }
  }

  const lockDemo = async () => {
    setLockError('')
    try {
      await api('/api/v1/demo/logout', { method: 'POST' })
      setActiveWorkspaceId(null)
      setWorkspaceReady(false)
      setAccessState('locked')
    } catch (error) {
      setLockError(error instanceof Error ? error.message : 'Could not lock the demo')
    }
  }

  useEffect(() => {
    document.documentElement.lang = locale === 'hi' ? 'hi' : 'en'
  }, [locale])

  useEffect(() => {
    if (accessState !== 'open') return
    let active = true
    api<{items:any[]}>('/api/v1/workspaces')
      .then(async (data) => {
        if (!active) return
        const workspaceId = data.items[0]?.id
        if (!workspaceId) throw new Error('Local workspace could not be initialized')
        setActiveWorkspaceId(workspaceId)
        const name = data.items[0].name || 'My Workspace'
        localStorage.setItem('permitpilot-workspace-name', name)
        setWorkspaceName(name)
        setWorkspaceReady(true)
      })
      .catch((error) => {
        if (!active) return
        const networkFailure = error instanceof TypeError
          && /failed to fetch|networkerror|load failed/i.test(error.message)
        setWorkspaceError(networkFailure
          ? 'network_unavailable'
          : error instanceof Error ? error.message : 'Could not load the local workspace')
      })
    return () => { active = false }
  }, [workspaceAttempt, accessState])

  useEffect(() => {
    const move = (event: MouseEvent) => {
      document.documentElement.style.setProperty('--mx', `${event.clientX}px`)
      document.documentElement.style.setProperty('--my', `${event.clientY}px`)
    }
    window.addEventListener('mousemove', move)
    return () => window.removeEventListener('mousemove', move)
  }, [])

  const displayWorkspaceError = workspaceError === 'network_unavailable'
    ? `${translate('Cannot reach the local PermitPilot API at', locale)} ${API_BASE}. ${translate('Start the backend with:', locale)} python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
    : translate(workspaceError, locale)

  if (PRIVATE_DEMO_MODE && accessState !== 'open') {
    return <PrivateDemoGate
      locale={locale}
      status={accessState}
      error={accessError}
      onLocaleChange={changeLocale}
      onRetry={() => {
        setAccessError('')
        setAccessState('checking')
        setAccessAttempt((attempt) => attempt + 1)
      }}
      onUnlock={(event) => void unlockDemo(event)}
    />
  }

  if (showLanding) {
    return <LandingPage
      locale={locale}
      onLocaleChange={changeLocale}
      onOpenWorkspace={(destination) => { setView(destination); setShowLanding(false) }}
    />
  }

  if (!workspaceReady) {
    return (
      <main className="auth-screen">
        <section className="auth-card">
          <p className="eyebrow">{translate(workspaceError ? 'WORKSPACE UNAVAILABLE' : 'STARTING PERMITPILOT', locale)}</p>
          <h1>{translate(workspaceError ? 'Could not open your workspace' : 'Preparing your dashboard...', locale)}</h1>
          {workspaceError && <><p className="auth-error">{displayWorkspaceError}</p><button onClick={() => { setWorkspaceError(''); setWorkspaceAttempt((attempt) => attempt + 1) }}>{translate('Retry connection', locale)}</button></>}
        </section>
      </main>
    )
  }

  return (
    <main className="app-shell">
      <div className="cursor-glow" />
      <div className="cursor-crosshair" />
      <div className={mobileOpen ? 'sidebar-wrap open' : 'sidebar-wrap'}><button className="sidebar-close" onClick={() => setMobileOpen(false)}><X size={18} /></button><Sidebar view={view} workspaceName={workspaceName} locale={locale} setView={(next) => { setView(next); setMobileOpen(false) }} /></div>
      {mobileOpen && <button className="mobile-backdrop" onClick={() => setMobileOpen(false)} aria-label={translate('Close navigation', locale)} />}
      <section className="workspace">
        <Topbar openMobile={() => setMobileOpen(true)} setView={setView} locale={locale} onLocaleChange={changeLocale} onLockDemo={PRIVATE_DEMO_MODE ? () => void lockDemo() : undefined} />
        <div className="workspace-content">
          {lockError && <p className="agent-error" role="alert">{translate(lockError, locale)}</p>}
          {view === 'overview' && <Overview setView={setView} locale={locale} />}
          {view === 'agent' && <AgentNavigator locale={locale} />}
          {view === 'onboarding' && <Onboarding locale={locale} />}
          {view === 'compliance' && <Compliance locale={locale} />}
          {view === 'documents' && <Documents locale={locale} />}
          {view === 'tasks' && <TasksPage locale={locale} />}
          {view === 'radar' && <Radar locale={locale} />}
          {view === 'simulator' && <Simulator locale={locale} />}
          {view === 'reports' && <Reports locale={locale} />}
          {view === 'membership' && <MembershipPage locale={locale} />}
          {view === 'settings' && <SettingsPage onWorkspaceNameChange={setWorkspaceName} locale={locale} />}
        </div>
      </section>
    </main>
  )
}

export default App
