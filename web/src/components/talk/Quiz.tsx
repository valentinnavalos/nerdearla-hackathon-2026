import { useState } from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { Lang, QuizQuestion } from "@/types/session"

const LABELS = {
  es: { score: "Puntaje", answered: "respondidas", retry: "Reintentar", correct: "¡Correcto!", wrong: "Incorrecto" },
  en: { score: "Score", answered: "answered", retry: "Try again", correct: "Correct!", wrong: "Wrong" },
}

interface QuizProps {
  questions: QuizQuestion[]
  lang: Lang
}

export function Quiz({ questions, lang }: QuizProps) {
  const [answers, setAnswers] = useState<(number | null)[]>(() => questions.map(() => null))
  const t = LABELS[lang]
  const answered = answers.filter((a) => a !== null).length
  const score = answers.filter((a, i) => a === questions[i].answer_idx).length

  return (
    <div className="space-y-6">
      {questions.map((q, qi) => {
        const chosen = answers[qi]
        const options = lang === "es" ? q.options_es : q.options_en
        return (
          <fieldset key={qi} className="space-y-2">
            <legend className="mb-2 font-medium">
              {qi + 1}. {lang === "es" ? q.q_es : q.q_en}
            </legend>
            <div className="grid gap-2">
              {options.map((opt, oi) => {
                const isAnswer = oi === q.answer_idx
                return (
                  <button
                    key={oi}
                    type="button"
                    disabled={chosen !== null}
                    onClick={() => setAnswers((prev) => prev.map((a, i) => (i === qi ? oi : a)))}
                    className={cn(
                      "rounded-lg border border-border px-3 py-2 text-left text-sm transition-colors",
                      chosen === null && "hover:bg-accent",
                      chosen !== null && isAnswer && "border-green-600 bg-green-600/10",
                      chosen === oi && !isAnswer && "border-destructive bg-destructive/10",
                    )}
                  >
                    {opt}
                  </button>
                )
              })}
            </div>
            {chosen !== null && (
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-foreground">
                  {chosen === q.answer_idx ? t.correct : t.wrong}
                </span>{" "}
                {lang === "es" ? q.explanation_es : q.explanation_en}
              </p>
            )}
          </fieldset>
        )
      })}
      <div className="flex items-center justify-between rounded-lg border border-border p-3">
        <span className="font-medium">
          {t.score}: {score}/{questions.length}
          {answered < questions.length && (
            <span className="font-normal text-muted-foreground">
              {" "}
              · {answered}/{questions.length} {t.answered}
            </span>
          )}
        </span>
        <Button variant="outline" size="sm" onClick={() => setAnswers(questions.map(() => null))}>
          {t.retry}
        </Button>
      </div>
    </div>
  )
}
