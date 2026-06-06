import { useState, useRef, useEffect } from 'react'
import { MessageCircle, X, Send, Bot } from 'lucide-react'
import axios from 'axios'

const LEX_ENDPOINT = import.meta.env.VITE_LEX_ENDPOINT || '/api/v1/webhooks/lex-fulfillment'

export default function DonorChatWidget({ donorId, requestId, notificationId }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([
    {
      id: 1,
      speaker: 'bot',
      text: "Hi! I'm your BloodBridge assistant. I can help you confirm, reschedule, or decline your donation request. How can I help?",
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || sending) return

    const userMsg = { id: Date.now(), speaker: 'user', text }
    setMessages((m) => [...m, userMsg])
    setInput('')
    setSending(true)

    try {
      const res = await axios.post(LEX_ENDPOINT, {
        inputTranscript: text,
        sessionState: {
          sessionAttributes: {
            donor_id: donorId || '',
            request_id: requestId || '',
            notification_id: notificationId || '',
          },
        },
      })
      const botText = res.data?.messages?.[0]?.content || "I didn't quite catch that. Try: YES, RESCHEDULE, or NO."
      setMessages((m) => [...m, { id: Date.now() + 1, speaker: 'bot', text: botText }])
    } catch {
      setMessages((m) => [
        ...m,
        { id: Date.now() + 1, speaker: 'bot', text: 'Sorry, I could not connect right now. Please call 1800-XXX-XXXX.' },
      ])
    } finally {
      setSending(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <>
      {/* FAB */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 bg-red-600 hover:bg-red-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all z-50"
          aria-label="Open chat"
        >
          <MessageCircle className="w-6 h-6" />
        </button>
      )}

      {/* Chat window */}
      {open && (
        <div className="fixed bottom-6 right-6 w-80 h-[450px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-red-600 rounded-t-2xl">
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-white" />
              <div>
                <p className="text-white text-sm font-semibold">BloodBridge Assistant</p>
                <p className="text-red-200 text-xs">Online</p>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="text-white hover:text-red-200">
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.speaker === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                    msg.speaker === 'user'
                      ? 'bg-red-600 text-white rounded-tr-sm'
                      : 'bg-slate-100 text-slate-800 rounded-tl-sm'
                  }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bg-slate-100 rounded-2xl rounded-tl-sm px-4 py-2">
                  <span className="text-slate-400 text-sm animate-pulse">Typing…</span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Quick replies */}
          <div className="px-3 pb-2 flex gap-1.5 flex-wrap">
            {['Yes, I confirm', 'Reschedule', 'No, decline', 'Help'].map((q) => (
              <button
                key={q}
                onClick={() => { setInput(q); setTimeout(sendMessage, 100) }}
                className="text-xs bg-slate-100 hover:bg-red-50 hover:text-red-700 text-slate-600 px-2.5 py-1 rounded-full transition-colors border border-slate-200"
              >
                {q}
              </button>
            ))}
          </div>

          {/* Input */}
          <div className="px-3 pb-3">
            <div className="flex items-center gap-2 border border-slate-200 rounded-xl px-3 py-2 focus-within:border-red-400">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Type your response..."
                className="flex-1 text-sm outline-none bg-transparent text-slate-800 placeholder-slate-400"
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || sending}
                className="text-red-600 disabled:text-slate-300 hover:text-red-700"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
