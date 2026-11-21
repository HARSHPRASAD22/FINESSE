import { useEffect, useState } from 'react'
import { Languages, Square, Volume2 } from 'lucide-react'
import { translate, type Locale } from '../lib/i18n'

function splitSpeech(text: string, limit = 900): string[] {
  const chunks: string[] = []
  let chunk = ''
  for (const sentence of text.match(/[^.!?।]+[.!?।]*/g) || [text]) {
    const next = `${chunk} ${sentence}`.trim()
    if (chunk && next.length > limit) {
      chunks.push(chunk)
      chunk = sentence.trim()
    } else {
      chunk = next
    }
  }
  if (chunk) chunks.push(chunk)
  return chunks
}

export default function LanguageVoiceControls({
  locale,
  onLocaleChange,
  targetSelector,
}: {
  locale: Locale
  onLocaleChange: (locale: Locale) => void
  targetSelector: string
}) {
  const [speaking, setSpeaking] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => () => window.speechSynthesis?.cancel(), [locale])

  const stopReading = () => {
    window.speechSynthesis?.cancel()
    setSpeaking(false)
    setMessage('')
  }

  const readPage = () => {
    if (!('speechSynthesis' in window)) {
      setMessage(translate('Voice playback is not supported in this browser.', locale))
      return
    }
    const page = document.querySelector<HTMLElement>(targetSelector)
    if (!page) return
    const copy = page.cloneNode(true) as HTMLElement
    copy.querySelectorAll('.language-voice-controls, [aria-hidden="true"]').forEach((element) => element.remove())
    copy.querySelectorAll('input, textarea, select').forEach((element) => {
      const control = element as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
      if (control instanceof HTMLInputElement && control.type === 'password') {
        control.remove()
        return
      }
      const value = control.value || (control instanceof HTMLInputElement ? control.placeholder : '')
      control.replaceWith(document.createTextNode(value))
    })
    const text = copy.innerText.replace(/\s+/g, ' ').trim()
    if (!text) {
      setMessage(translate('Could not start voice playback. Check that your browser has a Hindi or English voice installed.', locale))
      return
    }

    const speech = window.speechSynthesis
    speech.cancel()
    const voices = speech.getVoices()
    const chunks = splitSpeech(text)
    setSpeaking(true)
    setMessage(translate('Reading the page', locale))
    chunks.forEach((chunk, index) => {
      const utterance = new SpeechSynthesisUtterance(chunk)
      const voicePrefix = /[\u0900-\u097f]/.test(chunk) ? 'hi' : 'en'
      utterance.lang = voicePrefix === 'hi' ? 'hi-IN' : 'en-IN'
      const voice = voices.find((candidate) => candidate.lang.toLowerCase() === `${voicePrefix}-in`)
        || voices.find((candidate) => candidate.lang.toLowerCase().startsWith(voicePrefix))
      if (voice) utterance.voice = voice
      utterance.onend = () => {
        if (index === chunks.length - 1) {
          setSpeaking(false)
          setMessage('')
        }
      }
      utterance.onerror = () => {
        setSpeaking(false)
        setMessage(translate('Could not start voice playback. Check that your browser has a Hindi or English voice installed.', locale))
      }
      speech.speak(utterance)
    })
  }

  return (
    <div
      className="language-voice-controls"
      title={`${translate('Voice reads the main content only using your selected voice. Official source text and your entered details stay in their original language.', locale)} ${translate('Hindi interface translations cover the landing page and all workspace screens. Official source text, dynamic records, and user-entered content remain in their original language.', locale)}`}
    >
      <label>
        <Languages size={14} aria-hidden="true" />
        <span className="sr-only">{translate('Language', locale)}</span>
        <select value={locale} onChange={(event) => { stopReading(); onLocaleChange(event.target.value as Locale) }} aria-label={translate('Language', locale)}>
          <option value="en">{translate('English', locale)}</option>
          <option value="hi">{translate('Hindi', locale)}</option>
        </select>
      </label>
      {speaking
        ? <button onClick={stopReading} aria-label={translate('Stop reading', locale)} title={translate('Stop reading', locale)}><Square size={14} /><span>{translate('Stop reading', locale)}</span></button>
        : <button onClick={readPage} aria-label={translate('Listen', locale)} title={translate('Listen', locale)}><Volume2 size={15} /><span>{translate('Listen', locale)}</span></button>}
      {message && <span className="language-voice-controls__message" role="status">{message}</span>}
    </div>
  )
}
