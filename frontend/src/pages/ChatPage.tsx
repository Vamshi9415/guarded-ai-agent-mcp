import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  IconButton,
  List,
  ListItemButton,
  ListItemSecondaryAction,
  ListItemText,
  Paper,
  Skeleton,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import RefreshIcon from '@mui/icons-material/Refresh'
import SendIcon from '@mui/icons-material/Send'
import SmartToyIcon from '@mui/icons-material/SmartToy'
import PersonIcon from '@mui/icons-material/Person'
import { useDeleteConversation, useConversations, useResetConversation } from '../hooks/useConversation'
import { useSendMessage } from '../hooks/useChat'
import type { ConversationSummary } from '../types/chat'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LocalMessage {
  role: 'user' | 'assistant'
  content: string
  ts: number
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

function MessageBubble({ role, content }: { role: 'user' | 'assistant'; content: string }) {
  const isUser = role === 'user'
  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        mb: 1.5,
        gap: 1,
        alignItems: 'flex-end',
      }}
    >
      {!isUser && (
        <Box
          sx={{
            width: 30,
            height: 30,
            borderRadius: '50%',
            bgcolor: 'primary.main',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            mb: 0.5,
          }}
        >
          <SmartToyIcon sx={{ fontSize: 16, color: '#fff' }} />
        </Box>
      )}
      <Box
        sx={{
          maxWidth: '72%',
          px: 2,
          py: 1.25,
          borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          bgcolor: isUser ? 'primary.main' : 'background.paper',
          color: isUser ? 'primary.contrastText' : 'text.primary',
          border: isUser ? 'none' : 1,
          borderColor: 'divider',
          boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
          wordBreak: 'break-word',
          whiteSpace: 'pre-wrap',
        }}
      >
        <Typography variant="body2" lineHeight={1.6}>
          {content}
        </Typography>
      </Box>
      {isUser && (
        <Box
          sx={{
            width: 30,
            height: 30,
            borderRadius: '50%',
            bgcolor: 'secondary.main',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            mb: 0.5,
          }}
        >
          <PersonIcon sx={{ fontSize: 16, color: '#fff' }} />
        </Box>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Streaming indicator (typing dots)
// ---------------------------------------------------------------------------

function TypingIndicator() {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
      <Box
        sx={{
          width: 30,
          height: 30,
          borderRadius: '50%',
          bgcolor: 'primary.main',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <SmartToyIcon sx={{ fontSize: 16, color: '#fff' }} />
      </Box>
      <Box
        sx={{
          px: 2,
          py: 1.25,
          borderRadius: '18px 18px 18px 4px',
          bgcolor: 'background.paper',
          border: 1,
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
        }}
      >
        {[0, 1, 2].map((i) => (
          <Box
            key={i}
            sx={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              bgcolor: 'text.disabled',
              animation: 'pulse 1.2s ease-in-out infinite',
              animationDelay: `${i * 0.2}s`,
              '@keyframes pulse': {
                '0%, 100%': { opacity: 0.3, transform: 'scale(0.8)' },
                '50%': { opacity: 1, transform: 'scale(1)' },
              },
            }}
          />
        ))}
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// Conversation list item
// ---------------------------------------------------------------------------

function ConversationItem({
  conv,
  selected,
  onSelect,
  onDelete,
  onReset,
}: {
  conv: ConversationSummary
  selected: boolean
  onSelect: () => void
  onDelete: () => void
  onReset: () => void
}) {
  return (
    <ListItemButton
      selected={selected}
      onClick={onSelect}
      dense
      sx={{
        borderRadius: 1.5,
        mb: 0.5,
        pr: 7,
        '&.Mui-selected': {
          bgcolor: 'primary.50',
          '&:hover': { bgcolor: 'primary.100' },
        },
      }}
    >
      <ListItemText
        primary={
          <Typography variant="body2" fontWeight={selected ? 600 : 400} noWrap>
            {conv.conversation_id.slice(0, 8)}…
          </Typography>
        }
        secondary={
          <Typography variant="caption" color="text.disabled" noWrap>
            {formatTime(conv.created_at)} · {conv.message_count} msg
          </Typography>
        }
      />
      <ListItemSecondaryAction>
        <Tooltip title="Reset conversation">
          <IconButton size="small" onClick={(e) => { e.stopPropagation(); onReset() }}>
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Tooltip title="Delete conversation">
          <IconButton size="small" color="error" onClick={(e) => { e.stopPropagation(); onDelete() }}>
            <DeleteOutlineIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </ListItemSecondaryAction>
    </ListItemButton>
  )
}

// ---------------------------------------------------------------------------
// Main ChatPage
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<LocalMessage[]>([])
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: conversations, isLoading: convsLoading } = useConversations()
  const sendMutation = useSendMessage()
  const resetMutation = useResetConversation()
  const deleteMutation = useDeleteConversation()

  // Auto-scroll to bottom whenever messages change or typing indicator appears
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sendMutation.isPending])

  const handleNewConversation = useCallback(() => {
    setActiveConversationId(null)
    setMessages([])
    setInput('')
  }, [])

  const handleSelectConversation = useCallback((conv: ConversationSummary) => {
    // When switching convs we just clear local history and let the user re-query.
    // Full history retrieval would need a GET /chat/{id}/messages endpoint
    // (not yet in the backend spec), so we start fresh per conversation switch.
    setActiveConversationId(conv.conversation_id)
    setMessages([])
  }, [])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || sendMutation.isPending) return

    const userMsg: LocalMessage = { role: 'user', content: text, ts: Date.now() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')

    try {
      const result = await sendMutation.mutateAsync({
        conversation_id: activeConversationId,
        message: text,
      })
      // If this was a new conversation, pin the returned ID
      if (!activeConversationId) {
        setActiveConversationId(result.conversation_id)
      }
      const assistantMsg: LocalMessage = {
        role: 'assistant',
        content: result.reply,
        ts: Date.now(),
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to send message.'
      const errorMsg: LocalMessage = {
        role: 'assistant',
        content: `⚠️ Error: ${message}`,
        ts: Date.now(),
      }
      setMessages((prev) => [...prev, errorMsg])
    }
  }, [input, activeConversationId, sendMutation])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend],
  )

  const handleReset = useCallback(
    async (id: string) => {
      await resetMutation.mutateAsync(id)
      if (activeConversationId === id) {
        setMessages([])
      }
    },
    [activeConversationId, resetMutation],
  )

  const handleDelete = useCallback(
    async (id: string) => {
      await deleteMutation.mutateAsync(id)
      if (activeConversationId === id) {
        setActiveConversationId(null)
        setMessages([])
      }
    },
    [activeConversationId, deleteMutation],
  )

  const isEmpty = messages.length === 0 && !sendMutation.isPending

  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 128px)', gap: 0, overflow: 'hidden' }}>
      {/* ------------------------------------------------------------------ */}
      {/* Conversation sidebar                                                 */}
      {/* ------------------------------------------------------------------ */}
      <Paper
        variant="outlined"
        sx={{
          width: 260,
          flexShrink: 0,
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          borderRadius: 2,
          overflow: 'hidden',
          mr: 2,
        }}
      >
        <Box sx={{ p: 1.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="subtitle2" fontWeight={700}>
            Conversations
          </Typography>
          <Tooltip title="New conversation">
            <IconButton size="small" color="primary" onClick={handleNewConversation}>
              <AddIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        <Divider />
        <Box sx={{ flex: 1, overflowY: 'auto', p: 1 }}>
          {convsLoading ? (
            [1, 2, 3].map((i) => (
              <Skeleton key={i} height={52} sx={{ borderRadius: 1.5, mb: 0.5 }} />
            ))
          ) : !conversations?.length ? (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              <Typography variant="body2" color="text.disabled">
                No conversations yet.
              </Typography>
              <Typography variant="caption" color="text.disabled">
                Send a message to start.
              </Typography>
            </Box>
          ) : (
            <List disablePadding>
              {conversations.map((conv) => (
                <ConversationItem
                  key={conv.conversation_id}
                  conv={conv}
                  selected={conv.conversation_id === activeConversationId}
                  onSelect={() => handleSelectConversation(conv)}
                  onDelete={() => handleDelete(conv.conversation_id)}
                  onReset={() => handleReset(conv.conversation_id)}
                />
              ))}
            </List>
          )}
        </Box>
      </Paper>

      {/* ------------------------------------------------------------------ */}
      {/* Main chat area                                                       */}
      {/* ------------------------------------------------------------------ */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          gap: 1,
        }}
      >
        {/* Chat header */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
          <Box>
            <Typography variant="h6" fontWeight={700}>
              {activeConversationId
                ? `Conversation ${activeConversationId.slice(0, 8)}…`
                : 'New Conversation'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Guarded agent · POST /api/chat
            </Typography>
          </Box>
          <Button
            size="small"
            startIcon={<AddIcon />}
            onClick={handleNewConversation}
            variant="outlined"
            sx={{ display: { xs: 'inline-flex', md: 'none' } }}
          >
            New
          </Button>
        </Box>

        {/* Messages area */}
        <Paper
          variant="outlined"
          sx={{
            flex: 1,
            overflowY: 'auto',
            p: 2,
            borderRadius: 2,
            bgcolor: 'grey.50',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {isEmpty && (
            <Box
              sx={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 1.5,
                color: 'text.disabled',
              }}
            >
              <SmartToyIcon sx={{ fontSize: 48 }} />
              <Typography variant="body1" fontWeight={600}>
                Start a conversation
              </Typography>
              <Typography variant="body2" color="text.disabled" textAlign="center">
                Type a message below to interact with the guarded agent.
                <br />
                Policy rules will be applied to every request.
              </Typography>
            </Box>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} role={msg.role} content={msg.content} />
          ))}

          {sendMutation.isPending && <TypingIndicator />}

          {/* Scroll anchor */}
          <div ref={bottomRef} />
        </Paper>

        {/* Error alert */}
        {sendMutation.isError && (
          <Alert
            severity="error"
            variant="outlined"
            onClose={() => sendMutation.reset()}
            sx={{ py: 0.5 }}
          >
            {sendMutation.error?.message}
          </Alert>
        )}

        {/* Input row */}
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            fullWidth
            multiline
            maxRows={4}
            size="small"
            placeholder="Message the guarded agent… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sendMutation.isPending}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
            aria-label="Message input"
          />
          <Tooltip title="Send (Enter)">
            <span>
              <Button
                variant="contained"
                onClick={handleSend}
                disabled={!input.trim() || sendMutation.isPending}
                sx={{ borderRadius: 2, minWidth: 48, px: 1.5 }}
                aria-label="Send message"
              >
                {sendMutation.isPending ? (
                  <CircularProgress size={20} color="inherit" />
                ) : (
                  <SendIcon />
                )}
              </Button>
            </span>
          </Tooltip>
        </Box>
      </Box>
    </Box>
  )
}
