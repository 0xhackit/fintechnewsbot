/**
 * Telegram Bot API client.
 * Simple HTTP POST — no SDK needed.
 */

export interface TelegramResult {
  messageId: number;
  success: boolean;
  error?: string;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Format an article as a Telegram HTML message.
 * Matches the format from post_alerts_now.py.
 */
export function formatTelegramMessage(
  title: string,
  snippet: string,
  url: string
): string {
  let message = `<b>${escapeHtml(title)}</b>\n\n`;
  if (snippet) {
    message += `${escapeHtml(snippet)}\n\n`;
  }
  message += `<a href="${url}">Read more</a>`;
  return message;
}

/**
 * Send an HTML message to the configured Telegram chat.
 */
export async function sendTelegramMessage(
  html: string
): Promise<TelegramResult> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;

  if (!token || !chatId) {
    return {
      messageId: 0,
      success: false,
      error: "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID",
    };
  }

  try {
    const resp = await fetch(
      `https://api.telegram.org/bot${token}/sendMessage`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text: html,
          parse_mode: "HTML",
          disable_web_page_preview: true,
        }),
      }
    );

    const data = (await resp.json()) as {
      ok?: boolean;
      result?: { message_id?: number };
      description?: string;
    };

    if (!data.ok) {
      return {
        messageId: 0,
        success: false,
        error: data.description || `Telegram API error (${resp.status})`,
      };
    }

    return {
      messageId: data.result?.message_id || 0,
      success: true,
    };
  } catch (err) {
    return {
      messageId: 0,
      success: false,
      error: err instanceof Error ? err.message : "Unknown Telegram error",
    };
  }
}

/**
 * Delete a previously sent message from the configured chat.
 * Telegram only allows a bot to delete its own channel posts while it holds
 * can_delete_messages, and refuses messages older than 48 hours — so this is
 * best-effort: the caller reports the failure rather than aborting the retract.
 */
export async function deleteTelegramMessage(
  messageId: number
): Promise<{ success: boolean; error?: string }> {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const chatId = process.env.TELEGRAM_CHAT_ID;

  if (!token || !chatId) {
    return { success: false, error: "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID" };
  }

  try {
    const resp = await fetch(`https://api.telegram.org/bot${token}/deleteMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, message_id: messageId }),
    });

    const data = (await resp.json()) as { ok?: boolean; description?: string };
    if (!data.ok) {
      return { success: false, error: data.description || `Telegram API error (${resp.status})` };
    }
    return { success: true };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : "Unknown Telegram error",
    };
  }
}
