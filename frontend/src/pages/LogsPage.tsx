import {
  Alert,
  Box,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useLogs } from "../hooks/useLogs";

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function formatMs(value: number) {
  return `${value.toFixed(1)} ms`;
}

function formatJson(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function outcomeColor(outcome: string):
  | "success"
  | "warning"
  | "error"
  | "default" {
  switch (outcome) {
    case "allowed":
      return "success";
    case "requires_approval":
      return "warning";
    case "denied":
      return "error";
    default:
      return "default";
  }
}

export default function LogsPage() {
  const { data: logs = [], isLoading, isError, error } = useLogs();

  return (
    <Box sx={{ display: "grid", gap: 3 }}>
      <Box>
        <Typography variant="h4" fontWeight={700}>
          Logs
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Audit trail for policy decisions and system actions.
        </Typography>
      </Box>

      {isLoading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
          <CircularProgress />
        </Box>
      ) : isError ? (
        <Alert severity="error">
          {error instanceof Error ? error.message : "Failed to load logs."}
        </Alert>
      ) : logs.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            No logs yet
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Audit entries will appear here once policy decisions and tool actions
            are recorded.
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Time</TableCell>
                <TableCell>Conversation</TableCell>
                <TableCell>Tool</TableCell>
                <TableCell>Outcome</TableCell>
                <TableCell>Execution</TableCell>
                <TableCell>Reason</TableCell>
                <TableCell>Arguments</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {logs.map((log, index) => (
                <TableRow key={`${log.timestamp}-${log.toolname}-${index}`} hover>
                  <TableCell sx={{ minWidth: 180 }}>
                    <Typography variant="body2">
                      {formatDate(log.timestamp)}
                    </Typography>
                  </TableCell>

                  <TableCell sx={{ minWidth: 150 }}>
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: "monospace",
                        fontSize: 12,
                        wordBreak: "break-all",
                      }}
                    >
                      {log.conversationId}
                    </Typography>
                  </TableCell>

                  <TableCell sx={{ minWidth: 140 }}>
                    <Typography variant="body2" fontWeight={600}>
                      {log.toolName}
                    </Typography>
                  </TableCell>

                  <TableCell sx={{ minWidth: 140 }}>
                    <Chip
                      size="small"
                      label={log.outcome}
                      color={outcomeColor(log.outcome)}
                      variant="filled"
                    />
                  </TableCell>

                  <TableCell sx={{ minWidth: 100 }}>
                    <Typography variant="body2">
                      {formatMs(log.executionTimeMs)}
                    </Typography>
                  </TableCell>

                  <TableCell sx={{ minWidth: 220 }}>
                    <Stack spacing={0.75}>
                      {log.reason ? (
                        <Typography variant="body2">{log.reason}</Typography>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          —
                        </Typography>
                      )}

                      {log.engineFailure ? (
                        <Chip
                          size="small"
                          label="Engine failure"
                          color="error"
                          variant="outlined"
                          sx={{ width: "fit-content" }}
                        />
                      ) : null}
                    </Stack>
                  </TableCell>

                  <TableCell sx={{ minWidth: 280, maxWidth: 360 }}>
                    <Box
                      component="pre"
                      sx={{
                        m: 0,
                        p: 1.25,
                        borderRadius: 1,
                        bgcolor: "grey.100",
                        overflowX: "auto",
                        fontSize: 12,
                        lineHeight: 1.5,
                        fontFamily: "monospace",
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                      }}
                    >
                      {formatJson(log.arguments)}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}