export default function ExplainPanel({ text }) {
  return (
    <blockquote
      className="rounded-lg px-4 py-3 italic text-xs leading-relaxed"
      style={{
        borderLeft: '3px solid #7c3aed',
        background: 'rgba(124,58,237,0.08)',
        color: '#c4b5fd',
        lineHeight: 1.7,
        animation: 'fadeIn 0.3s ease',
      }}
    >
      {text}
      <style>{`@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }`}</style>
    </blockquote>
  )
}