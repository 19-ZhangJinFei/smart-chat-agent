/** 已被拒绝的同一问题重试时替换旧占位，不产生重复失败消息。 */
export function beginTurn(messages, text) {
  for (let i = messages.length - 1; i > 0; i--) {
    const answer = messages[i]
    const user = messages[i - 1]
    if (answer.failed && answer.notAccepted && answer.retryText === text && user.pending && user.content === text) {
      messages.splice(i - 1, 2)
      i -= 1
    }
  }
  messages.push({ role: 'user', content: text, pending: true },
    { role: 'assistant', content: '', pending: true, tools_used: [] })
  return messages.length - 1
}

export function settleTurn(messages, index, saved) {
  if (saved.messages?.length === 2) messages.splice(index - 1, 2, ...saved.messages)
  else {
    messages[index - 1].pending = false
    messages[index].pending = false
  }
}
