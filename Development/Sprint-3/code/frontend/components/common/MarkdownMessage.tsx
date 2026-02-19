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
    <div className="max-w-none text-sm text-gray-200 leading-relaxed prose prose-invert prose-p:my-2 prose-li:my-1 prose-ul:my-2 prose-ol:my-2 prose-pre:my-3 prose-pre:bg-black/30 prose-pre:border prose-pre:border-white/10 prose-code:bg-white/10 prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-2 whitespace-pre-wrap">{children}</p>,
          ul: ({ children }) => <ul className="my-2 list-disc pl-5 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 list-decimal pl-5 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-gray-200">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
          em: ({ children }) => <em className="italic text-gray-100">{children}</em>,
          code: ({ children, className }) => {
            const isBlock = Boolean(className && className.includes("language-"));
            if (isBlock) {
              return <code className={className}>{children}</code>;
            }
            return <code className="rounded bg-white/10 px-1 py-0.5 text-xs text-gray-100">{children}</code>;
          },
          pre: ({ children }) => (
            <pre className="my-3 overflow-x-auto rounded-lg border border-white/10 bg-black/30 p-3 text-xs leading-relaxed text-gray-100">
              {children}
            </pre>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-blue-300 underline decoration-blue-400/70 underline-offset-2 hover:text-blue-200"
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
