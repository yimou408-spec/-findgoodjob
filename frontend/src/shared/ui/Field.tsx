import { PropsWithChildren } from "react";

type FieldProps = PropsWithChildren<{
  label: string;
  hint?: string;
  htmlFor?: string;
}>;

export function Field({ label, hint, htmlFor, children }: FieldProps) {
  return (
    <label className="field" htmlFor={htmlFor}>
      <div className="field-label-row">
        <span className="field-label">{label}</span>
        {hint && <span className="field-hint">{hint}</span>}
      </div>
      {children}
    </label>
  );
}
