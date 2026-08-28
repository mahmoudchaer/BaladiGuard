import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { SUPPORTED_LOCALES, type AppLocale } from '@/i18n';
import { useI18n } from '@/i18n/LocaleProvider';
import './LanguageSwitcher.css';

type LanguageSwitcherProps = {
  compact?: boolean;
};

export function LanguageSwitcher({ compact = false }: LanguageSwitcherProps) {
  const { locale, t, setLocalePreference } = useI18n();
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<Array<HTMLDivElement | null>>([]);
  const listId = useId();
  const activeOptionId = `${listId}-option-${activeIndex}`;

  const closeMenu = (restoreFocus: boolean) => {
    setOpen(false);
    if (restoreFocus) {
      queueMicrotask(() => triggerRef.current?.focus());
    }
  };

  const openMenu = () => {
    const selectedIndex = Math.max(
      0,
      SUPPORTED_LOCALES.findIndex((option) => option === locale),
    );
    setActiveIndex(selectedIndex);
    setOpen(true);
  };

  const choose = (option: AppLocale) => {
    setLocalePreference(option);
    closeMenu(true);
  };

  useEffect(() => {
    if (!open) return;
    queueMicrotask(() => optionRefs.current[activeIndex]?.focus());
  }, [open, activeIndex]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        closeMenu(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  const onTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (!open) openMenu();
    }
  };

  const onListKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeMenu(true);
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % SUPPORTED_LOCALES.length);
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex(
        (index) => (index - 1 + SUPPORTED_LOCALES.length) % SUPPORTED_LOCALES.length,
      );
      return;
    }
    if (event.key === 'Home') {
      event.preventDefault();
      setActiveIndex(0);
      return;
    }
    if (event.key === 'End') {
      event.preventDefault();
      setActiveIndex(SUPPORTED_LOCALES.length - 1);
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      const option = SUPPORTED_LOCALES[activeIndex];
      if (option) choose(option as AppLocale);
    }
  };

  return (
    <div
      ref={rootRef}
      className={`language-switcher${compact ? ' language-switcher--compact' : ''}${
        open ? ' language-switcher--open' : ''
      }`}
    >
      {compact ? null : (
        <>
          <p className="language-switcher__heading">{t('common.language')}</p>
          <p className="language-switcher__hint">{t('language.hint')}</p>
        </>
      )}
      <div className="language-switcher__control">
        <button
          ref={triggerRef}
          type="button"
          className="language-switcher__trigger"
          role="combobox"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={open ? activeOptionId : undefined}
          aria-label={t(`language.${locale}`)}
          data-testid="language-menu"
          onClick={() => (open ? closeMenu(true) : openMenu())}
          onKeyDown={onTriggerKeyDown}
        >
          <span>{t(`language.${locale}`)}</span>
          <span className="language-switcher__chevron" aria-hidden>
            ▾
          </span>
        </button>
        {open ? (
          <div
            id={listId}
            className="language-switcher__menu"
            role="listbox"
            tabIndex={-1}
            aria-label={t('a11y.languageGroup')}
            onKeyDown={onListKeyDown}
          >
            {SUPPORTED_LOCALES.map((option, index) => {
              const selected = option === locale;
              const active = index === activeIndex;
              return (
                <div
                  key={option}
                  id={`${listId}-option-${index}`}
                  ref={(node) => {
                    optionRefs.current[index] = node;
                  }}
                  role="option"
                  tabIndex={active ? 0 : -1}
                  aria-selected={selected}
                  className={`language-switcher__option${
                    selected ? ' language-switcher__option--selected' : ''
                  }${active ? ' language-switcher__option--active' : ''}`}
                  data-testid={`language-option-${option}`}
                  onClick={() => choose(option as AppLocale)}
                  onMouseEnter={() => setActiveIndex(index)}
                >
                  {t(`language.${option}`)}
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}
