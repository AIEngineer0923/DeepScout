"use client";

import { useEffect, useId, useRef } from "react";

export type TabItem = { id: string; label: string };

export function Tabs({
  items,
  value,
  onChange,
  ariaLabel,
}: {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  ariaLabel: string;
}) {
  const listId = useId();
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    refs.current = refs.current.slice(0, items.length);
  }, [items.length]);

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const index = items.findIndex((item) => item.id === value);
    if (index < 0) return;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      const next = items[(index + 1) % items.length];
      onChange(next.id);
      refs.current[(index + 1) % items.length]?.focus();
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      const next = items[(index - 1 + items.length) % items.length];
      onChange(next.id);
      refs.current[(index - 1 + items.length) % items.length]?.focus();
    }
    if (event.key === "Home") {
      event.preventDefault();
      onChange(items[0].id);
      refs.current[0]?.focus();
    }
    if (event.key === "End") {
      event.preventDefault();
      onChange(items[items.length - 1].id);
      refs.current[items.length - 1]?.focus();
    }
  }

  return (
    <div className="tabs" role="tablist" aria-label={ariaLabel} id={listId} onKeyDown={onKeyDown}>
      {items.map((item, index) => {
        const selected = item.id === value;
        return (
          <button
            key={item.id}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="tab"
            className={`tab ${selected ? "active" : ""}`}
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.id)}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
