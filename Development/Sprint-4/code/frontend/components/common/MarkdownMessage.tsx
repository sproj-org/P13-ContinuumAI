"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownMessageProps = {
  content: string;
};

export default function MarkdownMessage({ content }: MarkdownMessageProps) {
  if (!content) {
    return null;
  }

  return (
    <div className="max-w-none text-sm text-black leading-relaxed prose prose-p:my-2 prose-li:my-1 prose-ul:my-2 prose-ol:my-2 prose-pre:my-3 prose-pre:bg-slate-100 prose-pre:border prose-pre:border-slate-200 prose-code:bg-slate-100 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-2 whitespace-pre-wrap">{children}</p>,
          ul: ({ children }) => <ul className="my-2 list-disc pl-5 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 list-decimal pl-5 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-black">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-black">{children}</strong>,
          em: ({ children }) => <em className="italic text-slate-800">{children}</em>,
          code: ({ children, className }) => {
            const isBlock = Boolean(className && className.includes("language-"));
            if (isBlock) {
              return <code className={className}>{children}</code>;
            }
            return <code className="rounded bg-slate-100 px-1 py-0.5 text-xs text-slate-800">{children}</code>;
          },
          pre: ({ children }) => (
            <pre className="my-3 overflow-x-auto rounded-lg border border-slate-200 bg-slate-100 p-3 text-xs leading-relaxed text-slate-800">
              {children}
            </pre>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-indigo-600 underline decoration-indigo-400/70 underline-offset-2 hover:text-indigo-500"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
