import katex from 'katex'

export function renderMath(text: string): string {
  // Block math $$...$$
  let result = text.replace(/\$\$(.+?)\$\$/gs, (_, expr) => {
    return katex.renderToString(expr, { displayMode: true, throwOnError: false })
  })
  // Inline math $...$
  result = result.replace(/\$(.+?)\$/g, (_, expr) => {
    return katex.renderToString(expr, { displayMode: false, throwOnError: false })
  })
  return result
}
