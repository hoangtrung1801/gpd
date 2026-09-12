#!/usr/bin/env node
import { Command } from "commander";
import { spawn as nodeSpawn } from "node:child_process";
import { ApiClient, ApiClientError, EXIT_CODES, type ExitCode } from "@gpd/api-client";
import { findProjectConfig } from "@gpd/config";
import type { GpdConfig } from "@gpd/contracts";
import { defaultGitOps, type GitOps } from "./git.js";
import { createErrorEnvelope, createSuccessEnvelope } from "./output.js";
import { executeInit } from "./commands/init.js";
import { executeServerStart } from "./commands/server.js";
import { executeAdd } from "./commands/add.js";
import { executeTaskList, executeTaskSet, executeTaskShow } from "./commands/task.js";
import { executeFinish, executeStart, executeStatus } from "./commands/session.js";
import { executeContext } from "./commands/context.js";
import { executeAgent } from "./commands/agent.js";
import {
  executeKnowledgeConfirm,
  executeKnowledgeEdit,
  executeKnowledgeList,
  executeKnowledgeReject,
} from "./commands/knowledge.js";
import { executeDoctor } from "./commands/doctor.js";

export type CliRuntime = {
  cwd?: string;
  client?: ApiClient;
  git?: GitOps;
  config?: { path: string; value: GpdConfig };
  spawn?: typeof nodeSpawn;
  stdout?: (chunk: string) => void;
  stderr?: (chunk: string) => void;
  env?: Record<string, string | undefined>;
};

async function resolveConfigAndClient(runtime: CliRuntime): Promise<{
  client: ApiClient;
  config?: GpdConfig;
  configPath?: string;
}> {
  let config = runtime.config?.value;
  let configPath = runtime.config?.path;

  if (!config) {
    try {
      const found = await findProjectConfig(runtime.cwd);
      config = found.value;
      configPath = found.path;
    } catch {
      // Config may not exist yet (e.g. before init or for doctor/server-start)
    }
  }

  const client =
    runtime.client ||
    new ApiClient({
      baseUrl: config?.apiUrl || runtime.env?.GPD_API_URL || "http://127.0.0.1:7337",
    });

  return { client, config, configPath };
}

export async function runCli(
  args: string[],
  runtime: CliRuntime = {}
): Promise<{ exitCode: number; stdout: string; stderr: string }> {
  let stdoutBuffer = "";
  let stderrBuffer = "";

  const writeStdout = (text: string) => {
    stdoutBuffer += text;
    runtime.stdout?.(text);
  };

  const writeStderr = (text: string) => {
    stderrBuffer += text;
    runtime.stderr?.(text);
  };

  const git = runtime.git || defaultGitOps;
  const spawnImpl = runtime.spawn || nodeSpawn;
  const isJson = args.includes("--json");

  let commandExecuted = false;
  let executedExitCode: ExitCode = EXIT_CODES.SUCCESS;

  const handleSuccess = (
    data: unknown,
    humanText?: string,
    warnings: string[] = []
  ) => {
    commandExecuted = true;
    if (isJson) {
      const envelope = createSuccessEnvelope(data, warnings);
      writeStdout(JSON.stringify(envelope, null, 2) + "\n");
    } else if (humanText !== undefined) {
      writeStdout(humanText + "\n");
    }
  };

  const handleError = (err: unknown) => {
    commandExecuted = true;
    const { envelope, exitCode } = createErrorEnvelope(err);
    executedExitCode = exitCode;
    if (isJson) {
      writeStdout(JSON.stringify(envelope, null, 2) + "\n");
    } else {
      writeStderr(`Error: ${envelope.error?.message ?? String(err)}\n`);
    }
  };

  const program = new Command();
  program
    .name("gpd")
    .description("GPD Developer CLI")
    .option("--json", "Output response in JSON ApiEnvelope format")
    .exitOverride();

  // init
  program
    .command("init")
    .description("Initialize GPD in current repository")
    .option("--api-url <url>", "API URL for GPD backend")
    .option("--name <name>", "Project name")
    .action(async (opts) => {
      try {
        const { client } = await resolveConfigAndClient(runtime);
        const result = await executeInit(client, git, { apiUrl: opts.apiUrl, name: opts.name }, runtime.cwd);
        handleSuccess(result, `Initialized GPD project at ${result.configPath}`);
      } catch (err) {
        handleError(err);
      }
    });

  // server start / server-start
  const registerServerCommand = (cmd: Command) => {
    cmd
      .description("Start the GPD local server")
      .option("--host <host>", "Host to bind to", "127.0.0.1")
      .option("--port <port>", "Port to bind to", "7337")
      .option("--detach", "Run server in background", false)
      .action(async (opts) => {
        try {
          const { client } = await resolveConfigAndClient(runtime);
          const portNum = Number.parseInt(opts.port, 10) || 7337;
          const result = await executeServerStart(
            client,
            git,
            { host: opts.host, port: portNum, detach: opts.detach },
            spawnImpl,
            runtime.cwd
          );
          handleSuccess(
            result,
            opts.detach
              ? `GPD server started in background (PID: ${result.pid}) at http://${result.host}:${result.port}`
              : `GPD server started at http://${result.host}:${result.port}`
          );
        } catch (err) {
          handleError(err);
        }
      });
  };

  const serverCmd = program.command("server");
  registerServerCommand(serverCmd.command("start"));
  registerServerCommand(program.command("server-start"));

  // add <path>
  program
    .command("add <path>")
    .description("Add a document or specification to project knowledge")
    .action(async (targetPath) => {
      try {
        const { client, config } = await resolveConfigAndClient(runtime);
        if (!config) {
          throw new ApiClientError({
            message: "No .gpd/config.json found. Run 'gpd init' first.",
            code: "CONFIG_ERROR",
            status: 401,
          });
        }
        const result = await executeAdd(client, git, config, targetPath, runtime.cwd);
        handleSuccess(result, `Added source document '${result.path}' (id: ${result.id})`);
      } catch (err) {
        handleError(err);
      }
    });

  // task
  const taskCmd = program.command("task").description("Manage GPD tasks");

  taskCmd
    .command("list")
    .description("List tasks in the current project")
    .option("--status <status>", "Filter by status")
    .option("--query <query>", "Filter by search query")
    .action(async (opts) => {
      try {
        const { client, config } = await resolveConfigAndClient(runtime);
        if (!config) {
          throw new ApiClientError({
            message: "No .gpd/config.json found. Run 'gpd init' first.",
            code: "CONFIG_ERROR",
            status: 401,
          });
        }
        const result = await executeTaskList(client, config, opts);
        const text = (result.items || [])
          .map((t) => `[${t.public_id || t.id}] ${t.title} (${t.status}, ${t.priority})`)
          .join("\n") || "No tasks found";
        handleSuccess(result, text);
      } catch (err) {
        handleError(err);
      }
    });

  taskCmd
    .command("show <taskId>")
    .description("Show details of a task")
    .action(async (taskId) => {
      try {
        const { client } = await resolveConfigAndClient(runtime);
        const task = await executeTaskShow(client, taskId);
        const text = `Task: ${task.public_id || task.id}\nTitle: ${task.title}\nStatus: ${task.status}\nPriority: ${task.priority}\n\n${task.description}`;
        handleSuccess(task, text);
      } catch (err) {
        handleError(err);
      }
    });

  taskCmd
    .command("set <taskId>")
    .description("Set the active task in .gpd/config.json")
    .action(async (taskId) => {
      try {
        const { client, config, configPath } = await resolveConfigAndClient(runtime);
        if (!config || !configPath) {
          throw new ApiClientError({
            message: "No .gpd/config.json found. Run 'gpd init' first.",
            code: "CONFIG_ERROR",
            status: 401,
          });
        }
        const result = await executeTaskSet(client, config, configPath, taskId);
        handleSuccess(result, `Set current task to ${result.currentTaskId}`);
      } catch (err) {
        handleError(err);
      }
    });

  // start
  program
    .command("start")
    .description("Start a developer session with current Git context")
    .action(async () => {
      try {
        const { client, config } = await resolveConfigAndClient(runtime);
        if (!config) {
          throw new ApiClientError({
            message: "No .gpd/config.json found. Run 'gpd init' first.",
            code: "CONFIG_ERROR",
            status: 401,
          });
        }
        const session = await executeStart(client, git, config, runtime.cwd);
        const warnings = (session.overlap_warnings ?? []).map((w) => w.explanation);
        handleSuccess(session, `Session started: ${session.id}`, warnings);
      } catch (err) {
        handleError(err);
      }
    });

  // status
  program
    .command("status")
    .description("Show status of current task, session, and search health")
    .action(async () => {
      try {
        const { client, config } = await resolveConfigAndClient(runtime);
        if (!config) {
          throw new ApiClientError({
            message: "No .gpd/config.json found. Run 'gpd init' first.",
            code: "CONFIG_ERROR",
            status: 401,
          });
        }
        const result = await executeStatus(client, config);
        const text = [
          `Task: ${result.task ? `${result.task.public_id || result.task.id} (${result.task.title})` : "none"}`,
          `Session: ${result.session ? result.session.id : "none"}`,
          `Health: Database ${result.health?.database ?? "unknown"}, Search ${result.health?.search ?? "unknown"}`,
        ].join("\n");
        handleSuccess(result, text);
      } catch (err) {
        handleError(err);
      }
    });

  // context
  program
    .command("context")
    .description("Assemble and display budgeted project context")
    .option("--format <format>", "Format: text or json", "text")
    .action(async (opts) => {
      try {
        const { client, config } = await resolveConfigAndClient(runtime);
        if (!config) {
          throw new ApiClientError({
            message: "No .gpd/config.json found. Run 'gpd init' first.",
            code: "CONFIG_ERROR",
            status: 401,
          });
        }
        const requestedFormat = opts.format === "json" || isJson ? "json" : "text";
        const result = await executeContext(client, config, { format: requestedFormat });
        handleSuccess(result.context, result.text, result.warnings);
      } catch (err) {
        handleError(err);
      }
    });

  // agent "<prompt>"
  program
    .command("agent <prompt>")
    .description("Launch external coding agent with budgeted context")
    .action(async (prompt) => {
      try {
        const { client, config } = await resolveConfigAndClient(runtime);
        if (!config) {
          throw new ApiClientError({
            message: "No .gpd/config.json found. Run 'gpd init' first.",
            code: "CONFIG_ERROR",
            status: 401,
          });
        }
        const result = await executeAgent(client, git, config, prompt, {}, runtime.cwd);
        executedExitCode = result.exitCode as ExitCode;
        handleSuccess(result, `Agent exited with code ${result.exitCode}`);
      } catch (err) {
        handleError(err);
      }
    });

  // finish
  program
    .command("finish")
    .description("Finish active developer session and extract knowledge")
    .option("--summary <summary>", "Optional summary of changes")
    .action(async (opts) => {
      try {
        const { client, config } = await resolveConfigAndClient(runtime);
        if (!config) {
          throw new ApiClientError({
            message: "No .gpd/config.json found. Run 'gpd init' first.",
            code: "CONFIG_ERROR",
            status: 401,
          });
        }
        const result = await executeFinish(client, git, config, { summary: opts.summary }, runtime.cwd);
        handleSuccess(
          result,
          `Session ${result.session.id} finished. Generated ${result.proposals?.length ?? 0} knowledge proposals.`
        );
      } catch (err) {
        handleError(err);
      }
    });

  // knowledge review [confirm|edit|reject]
  const knowledgeCmd = program.command("knowledge").description("Review project knowledge");
  const reviewCmd = knowledgeCmd.command("review").description("Review pending knowledge proposals");

  reviewCmd.action(async () => {
    try {
      const { client, config } = await resolveConfigAndClient(runtime);
      if (!config) {
        throw new ApiClientError({
          message: "No .gpd/config.json found. Run 'gpd init' first.",
          code: "CONFIG_ERROR",
          status: 401,
        });
      }
      const proposals = await executeKnowledgeList(client, config);
      const text = proposals.map((p) => `[${p.id}] (${p.type}) ${p.title}`).join("\n") || "No pending proposals";
      handleSuccess(proposals, text);
    } catch (err) {
      handleError(err);
    }
  });

  reviewCmd
    .command("confirm <proposalId>")
    .description("Confirm a knowledge proposal")
    .action(async (proposalId) => {
      try {
        const { client } = await resolveConfigAndClient(runtime);
        const result = await executeKnowledgeConfirm(client, proposalId);
        handleSuccess(result, `Confirmed proposal ${proposalId}`);
      } catch (err) {
        handleError(err);
      }
    });

  reviewCmd
    .command("edit <proposalId> <content>")
    .description("Edit and confirm a knowledge proposal")
    .action(async (proposalId, content) => {
      try {
        const { client } = await resolveConfigAndClient(runtime);
        const result = await executeKnowledgeEdit(client, proposalId, content);
        handleSuccess(result, `Edited proposal ${proposalId}`);
      } catch (err) {
        handleError(err);
      }
    });

  reviewCmd
    .command("reject <proposalId> [reason]")
    .description("Reject a knowledge proposal")
    .action(async (proposalId, reason) => {
      try {
        const { client } = await resolveConfigAndClient(runtime);
        const result = await executeKnowledgeReject(client, proposalId, reason);
        handleSuccess(result, `Rejected proposal ${proposalId}`);
      } catch (err) {
        handleError(err);
      }
    });

  // doctor
  program
    .command("doctor")
    .description("Diagnose environment and backend health")
    .action(async () => {
      try {
        const { client, config, configPath } = await resolveConfigAndClient(runtime);
        const report = await executeDoctor(client, git, config, configPath, runtime.cwd);
        const text = report.checks
          .map((c) => `[${c.status.toUpperCase()}] ${c.name}: ${c.message}`)
          .join("\n");
        handleSuccess(report, text);
      } catch (err) {
        handleError(err);
      }
    });

  try {
    await program.parseAsync(args, { from: "user" });
  } catch (err: unknown) {
    if (!commandExecuted) {
      handleError(err);
    }
  }

  return {
    exitCode: executedExitCode,
    stdout: stdoutBuffer,
    stderr: stderrBuffer,
  };
}

// CLI direct execution
if (import.meta.url === `file://${process.argv[1]}`) {
  const result = await runCli(process.argv.slice(2));
  process.exit(result.exitCode);
}
