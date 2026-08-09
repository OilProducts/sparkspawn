import { memo, useMemo } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'

import { TranscriptCopyButton } from '@/components/app/transcript/TranscriptCopyButton'
import { cn } from '@/lib/utils'

const INLINE_CODE_CONTAINER_CLASS_NAME =
    '[&_code]:rounded [&_code]:border [&_code]:border-border/60 [&_code]:bg-background/80 [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[11px] [&_code]:text-foreground [&_code]:[overflow-wrap:anywhere]'

const markdownComponents: Components = {
    a({ children }) {
        return <span className="font-medium text-foreground">{children}</span>
    },
    blockquote({ children }) {
        return (
            <blockquote
                className={cn(
                    'border-l-2 border-border/80 pl-3 italic text-muted-foreground',
                    INLINE_CODE_CONTAINER_CLASS_NAME,
                )}
            >
                {children}
            </blockquote>
        )
    },
    code({ children, className }) {
        return <code className={cn('whitespace-pre-wrap break-words font-mono text-[11px] text-foreground [overflow-wrap:anywhere]', className)}>{children}</code>
    },
    em({ children }) {
        return <em className="italic text-foreground">{children}</em>
    },
    h1({ children }) {
        return (
            <h1 className={cn('text-sm font-semibold text-foreground', INLINE_CODE_CONTAINER_CLASS_NAME)}>
                {children}
            </h1>
        )
    },
    h2({ children }) {
        return (
            <h2 className={cn('text-sm font-semibold text-foreground', INLINE_CODE_CONTAINER_CLASS_NAME)}>
                {children}
            </h2>
        )
    },
    h3({ children }) {
        return (
            <h3 className={cn('text-xs font-semibold uppercase tracking-wide text-foreground', INLINE_CODE_CONTAINER_CLASS_NAME)}>
                {children}
            </h3>
        )
    },
    h4({ children }) {
        return (
            <h4 className={cn('text-xs font-semibold text-foreground', INLINE_CODE_CONTAINER_CLASS_NAME)}>
                {children}
            </h4>
        )
    },
    h5({ children }) {
        return (
            <h5 className={cn('text-xs font-semibold text-foreground', INLINE_CODE_CONTAINER_CLASS_NAME)}>
                {children}
            </h5>
        )
    },
    h6({ children }) {
        return (
            <h6 className={cn('text-xs font-semibold text-muted-foreground', INLINE_CODE_CONTAINER_CLASS_NAME)}>
                {children}
            </h6>
        )
    },
    img({ alt }) {
        if (!alt) {
            return null
        }

        return <span className="font-medium text-foreground">{alt}</span>
    },
    li({ children }) {
        return <li className={cn('break-words [overflow-wrap:anywhere]', INLINE_CODE_CONTAINER_CLASS_NAME)}>{children}</li>
    },
    ol({ children }) {
        return <ol className="list-decimal space-y-1 pl-5 text-xs leading-5 text-foreground">{children}</ol>
    },
    p({ children }) {
        return (
            <p className={cn('min-w-0 break-words text-xs leading-5 text-foreground [overflow-wrap:anywhere]', INLINE_CODE_CONTAINER_CLASS_NAME)}>
                {children}
            </p>
        )
    },
    pre({ children }) {
        return (
            <pre className="max-w-full overflow-x-hidden whitespace-pre-wrap break-words rounded border border-border/60 bg-background/80 px-3 py-2 [overflow-wrap:anywhere]">
                {children}
            </pre>
        )
    },
    strong({ children }) {
        return <strong className="font-semibold text-foreground">{children}</strong>
    },
    ul({ children }) {
        return <ul className="list-disc space-y-1 pl-5 text-xs leading-5 text-foreground">{children}</ul>
    },
}

interface ProjectConversationMarkdownProps {
    content: string
    enableCodeCopy?: boolean
}

const fencedCodeText = (source: string, start: number, end: number) => {
    const block = source.slice(start, end)
    const opening = block.match(/^[ \t]{0,3}(`{3,}|~{3,})[^\r\n]*(?:\r\n|\n|\r)/)
    if (!opening) return null
    const fence = opening[1]
    const body = block.slice(opening[0].length)
    const closing = body.match(new RegExp(`(^|\\r\\n|\\n|\\r)[ \\t]{0,3}${fence[0]}{${fence.length},}[ \\t]*(?:\\r\\n|\\n|\\r)?$`))
    return closing?.index === undefined ? body : body.slice(0, closing.index + closing[1].length)
}

function ProjectConversationMarkdownComponent({ content, enableCodeCopy = false }: ProjectConversationMarkdownProps) {
    const components = useMemo<Components>(() => enableCodeCopy ? {
        ...markdownComponents,
        pre({ children, node }) {
            const position = node?.position
            const text = position?.start.offset !== undefined && position.end.offset !== undefined
                ? fencedCodeText(content, position.start.offset, position.end.offset)
                : null
            return (
                <div className="relative">
                    <pre className="max-w-full overflow-x-hidden whitespace-pre-wrap break-words rounded border border-border/60 bg-background/80 px-3 py-2 pr-9 [overflow-wrap:anywhere]">
                        {children}
                    </pre>
                    {text !== null ? (
                        <span className="absolute right-1 top-1">
                            <TranscriptCopyButton label="Copy code" text={text} />
                        </span>
                    ) : null}
                </div>
            )
        },
    } : markdownComponents, [content, enableCodeCopy])

    return (
        <div className="min-w-0 space-y-2 break-words text-foreground [overflow-wrap:anywhere]">
            <ReactMarkdown components={components} skipHtml>
                {content}
            </ReactMarkdown>
        </div>
    )
}

export const ProjectConversationMarkdown = memo(ProjectConversationMarkdownComponent)
