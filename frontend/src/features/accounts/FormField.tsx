import { useId, type InputHTMLAttributes, type ReactNode } from 'react'

interface FieldProps {
  label: string
  error?: string
  hint?: ReactNode
  children: (props: {
    id: string
    'aria-invalid': boolean
    'aria-describedby': string | undefined
  }) => ReactNode
}

/** Label + control + hint + error, wired up for screen readers. */
export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className="field">
      <label htmlFor={id} className="field__label">
        {label}
      </label>
      {children({ id, 'aria-invalid': Boolean(error), 'aria-describedby': describedBy })}
      {hint && (
        <p id={hintId} className="field__hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="field__error">
          {error}
        </p>
      )}
    </div>
  )
}

interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: string
  error?: string
  hint?: ReactNode
}

export function TextField({ label, error, hint, ...input }: TextFieldProps) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(a11y) => <input className="field__input" {...a11y} {...input} />}
    </Field>
  )
}
