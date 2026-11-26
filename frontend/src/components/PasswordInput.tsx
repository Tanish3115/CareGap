"use client";

import { Eye, EyeOff, Lock } from "lucide-react";
import { useState, type ComponentPropsWithoutRef } from "react";
import { useLanguage } from "./LanguageProvider";

type Props = Omit<ComponentPropsWithoutRef<"input">, "type"> & {
  showLock?: boolean;
  wrapperClassName?: string;
};

export function PasswordInput({ showLock, wrapperClassName = "", ...props }: Props) {
  const { t } = useLanguage();
  const [visible, setVisible] = useState(false);
  const label = visible ? t("Hide password") : t("Show password");
  const Icon = visible ? EyeOff : Eye;
  return (
    <div className={`relative ${wrapperClassName}`}>
      {showLock && (
        <Lock
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
        />
      )}
      <input {...props} type={visible ? "text" : "password"} spellCheck={false} autoCapitalize="none" />
      <button
        type="button"
        aria-label={label}
        aria-controls={props.id}
        title={label}
        disabled={props.disabled}
        onClick={() => setVisible(!visible)}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-lg text-slate-600 hover:text-blue-700 focus-visible:outline-2"
      >
        <Icon aria-hidden="true" className="h-5 w-5" />
      </button>
    </div>
  );
}
