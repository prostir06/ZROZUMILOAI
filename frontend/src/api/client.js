import { BaseApiClient } from './base.js';
import { backupApiMethods } from './backups.js';
import { chatApiMethods } from './chats.js';
import { ollamaApiMethods } from './ollama.js';
import { telegramApiMethods } from './telegram.js';
import { workspaceApiMethods } from './workspaces.js';

export class ApiClient extends BaseApiClient {}

Object.assign(
  ApiClient.prototype,
  workspaceApiMethods,
  telegramApiMethods,
  chatApiMethods,
  ollamaApiMethods,
  backupApiMethods,
);

export const api = new ApiClient();
