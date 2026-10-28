import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";

import { cn } from "@/lib/cn";

/**
 * Only http(s), mailto and in-page links survive; anything else (javascript:, data:)
 * becomes an empty href. react-markdown's own transform already drops dangerous schemes;
 * this narrows it further for statements written by other people.
 */
export function safeUrl(url: string): string {
  const cleaned = defaultUrlTransform(url);
  if (!cleaned) return "";
  if (cleaned.startsWith("#") || cleaned.startsWith("/")) return cleaned;
  return /^(https?:|mailto:)/i.test(cleaned) ? cleaned : "";
}

/**
 * A problem statement: GitHub-flavoured Markdown with $math$ and $$display math$$.
 * Raw HTML in the source is not rendered (skipHtml), so a statement cannot inject
 * scripts, styles or frames.
 */
export function Markdown({ source, className }: { source: string; className?: string }) {
  return (
    <div className={cn("prose-statement", className)}>
      <ReactMarkdown
        skipHtml
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: "ignore" }]]}
        urlTransform={safeUrl}
        components={{
          a: ({ href, children }) => (
            <a href={href} target={href?.startsWith("http") ? "_blank" : undefined} rel="noopener noreferrer nofollow">
              {children}
            </a>
          ),
          img: ({ src, alt }) =>
            typeof src === "string" && safeUrl(src) ? (
              // Statement images are authored URLs unknown at build time, so next/image cannot optimise them.
              // eslint-disable-next-line @next/next/no-img-element
              <img src={safeUrl(src)} alt={alt ?? ""} className="max-w-full rounded-lg" loading="lazy" />
            ) : null,
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
