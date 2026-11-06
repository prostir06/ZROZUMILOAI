# Phase 1: Data Safety, Core Indexing & Backup Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Забезпечити 100% збереження даних при бекапах (дамп БД + директорія медіа `/app/media`), перенести декларацію HNSW векторного індексу в Django models і додати індекси для журналу чатів.

**Architecture:** Розширення `BackupService` підтримкою архівних пакетів `.tar.gz` (дамп бази + директорія `media/` + `manifest.json`) зі збереженням зворотної сумісності зі старими `.sql`/`.sqlite3` файлами. Декларування `pgvector.django.HnswIndex` безпосередньо у `DocumentChunk.Meta.indexes` для передбачуваних міграцій на нових інсталяціях, та додавання складених індексів у `WorkspaceChatLog`.

**Tech Stack:** Python 3.12, Django 5.x, DRF, PostgreSQL 16 + pgvector, tarfile, shutil.

## Global Constraints

- **Python & Django**: Python >= 3.12, Django >= 5.0, < 6.0.
- **Зворотна сумісність**: `BackupService` зобов'язаний розпізнавати та відновлювати як нові архіви `.tar.gz`, так і чисті `.sql` / `.sqlite3` дампи.
- **Дотримання ліцензій**: Жодних GPL/AGPL залежностей.
- **Безпека шляхів**: Запобігати Path Traversal у розпакуванні архіву (перевірка `resolved` шляхів).

---

### Task 1: Archive Bundle Creation in BackupService (Database + Media)

**Files:**
- Modify: `backend/backups/services.py:15-115`
- Test: `backend/backups/tests/test_services.py`

**Interfaces:**
- Consumes: `settings.BACKUP_DIR`, `settings.MEDIA_ROOT`, `settings.DATABASES`
- Produces: `BackupService.create_backup(include_media=True)` повертає dict з ключами `filename`, `size`, `created_at`, `engine`, `has_media`.

- [ ] **Step 1: Write failing unit test for creating an archive backup with media**

```python
# In backend/backups/tests/test_services.py
def test_create_backup_includes_media_when_requested(self, tmp_path, settings):
    media_dir = tmp_path / 'media' / 'workspace_documents' / '1'
    media_dir.mkdir(parents=True)
    sample_file = media_dir / 'test.pdf'
    sample_file.write_bytes(b'%PDF-1.4 sample content')

    settings.MEDIA_ROOT = str(tmp_path / 'media')
    backup_dir = tmp_path / 'backups'
    service = BackupService(backup_dir=backup_dir)

    info = service.create_backup(include_media=True)
    assert info['filename'].endswith('.tar.gz')
    assert (backup_dir / info['filename']).exists()
    assert info.get('has_media') is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/backups/tests/test_services.py -k test_create_backup_includes_media_when_requested`
Expected: FAIL with `unexpected keyword argument 'include_media'` або розширення не `.tar.gz`.

- [ ] **Step 3: Implement archive creation in BackupService**

Додати `.tar.gz` до `ALLOWED_EXTENSIONS` у `backend/backups/services.py`.
Створити метод `_pack_archive(db_dump_path, include_media=True)`:
1. Генерує `backup_{db_name}_{stamp}.tar.gz`.
2. Записує всередину tar-архіву файл дампа бази (наприклад, `dump.sql` або `dump.sqlite3`).
3. Якщо `include_media=True` і `settings.MEDIA_ROOT` існує — додає вміст директорії `workspace_documents` під відносним префіксом `media/workspace_documents`.
4. Записує `manifest.json` із версією та списком файлів.
5. Видаляє тимчасовий сирий `dump.sql`/`dump.sqlite3`, залишаючи лише цілісний `.tar.gz`.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/backups/tests/test_services.py -k test_create_backup_includes_media_when_requested`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add backend/backups/services.py backend/backups/tests/test_services.py
git commit -m "feat(backups): support full bundle backup with media directory"
```

---

### Task 2: Archive Restoration and Backward Compatibility in BackupService

**Files:**
- Modify: `backend/backups/services.py:160-275`
- Test: `backend/backups/tests/test_services.py`

**Interfaces:**
- Consumes: `BackupService.restore_latest_backup()`, `BackupService.restore_backup(filename)`
- Produces: Відновлення бази + розпакування файлів у `settings.MEDIA_ROOT`.

- [ ] **Step 1: Write failing unit test for restoring from .tar.gz archive and legacy .sql**

```python
# In backend/backups/tests/test_services.py
def test_restore_archive_restores_database_and_media(self, tmp_path, settings):
    media_dir = tmp_path / 'media'
    target_doc = media_dir / 'workspace_documents' / '1' / 'doc.txt'
    target_doc.parent.mkdir(parents=True)
    target_doc.write_text('Original text')

    settings.MEDIA_ROOT = str(media_dir)
    backup_dir = tmp_path / 'backups'
    service = BackupService(backup_dir=backup_dir)

    backup_info = service.create_backup(include_media=True)

    # Simulate media deletion
    target_doc.unlink()
    assert not target_doc.exists()

    # Restore
    service.restore_backup(backup_info['filename'])
    assert target_doc.exists()
    assert target_doc.read_text() == 'Original text'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/backups/tests/test_services.py -k test_restore_archive_restores_database_and_media`
Expected: FAIL

- [ ] **Step 3: Implement archive restoration logic**

1. У методі `_resolve_safe_path` додати валідацію `filename.endswith('.tar.gz')`.
2. Якщо файл закінчується на `.tar.gz`:
   - Безпечно вилучити `dump.sql` або `dump.sqlite3` у тимчасову папку (перевіряючи захист від Path Traversal `os.path.commonpath`).
   - Якщо присутня папка `media/` у тарболі — розпакувати файли у `settings.MEDIA_ROOT`.
   - Запустити стандартне відновлення БД (`_restore_postgresql` або `_restore_sqlite`).
   - Очистити тимчасові розпаковані файли дампа.
3. Якщо файл закінчується на `.sql` або `.sqlite3` — виконати відновлення як і раніше (legacy fallback).

- [ ] **Step 4: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/backups/tests/test_services.py`
Expected: ALL PASS

- [ ] **Step 5: Commit changes**

```bash
git add backend/backups/services.py backend/backups/tests/test_services.py
git commit -m "feat(backups): implement archive bundle restore with media unpack"
```

---

### Task 3: Update Backup Scripts & Management Commands

**Files:**
- Modify: `scripts/backup-cron.sh`
- Modify: `scripts/backup-cron.ps1`
- Modify: `backend/backups/management/commands/create_backup.py`
- Modify: `backend/backups/management/commands/restore_backup.py`

**Interfaces:**
- CLI: `python manage.py create_backup [--no-media]`
- CLI: `python manage.py restore_backup [filename]`

- [ ] **Step 1: Write test for create_backup and restore_backup management commands**

```python
# In backend/backups/tests/test_commands.py
from django.core.management import call_command

def test_create_and_restore_backup_command(tmp_path, settings):
    settings.BACKUP_DIR = str(tmp_path / 'backup')
    call_command('create_backup')
    service = BackupService(backup_dir=settings.BACKUP_DIR)
    assert service.find_latest_backup() is not None
```

- [ ] **Step 2: Update management commands to accept options and log media status**

Оновити `create_backup.py` та `restore_backup.py` з підтримкою нових параметрів та інформаційного виводу.

- [ ] **Step 3: Update scripts/backup-cron.sh to maintain .tar.gz archives**

Оновити регулярні вирази пошуку та ротації за `BACKUP_KEEP_DAYS`, щоб очищувати як старі `.sql`, так і нові `.tar.gz` архіви.

- [ ] **Step 4: Commit changes**

```bash
git add scripts/backup-cron.sh scripts/backup-cron.ps1 backend/backups/management/commands/
git commit -m "feat(backups): update cron scripts and management commands for bundle archives"
```

---

### Task 4: Declare HnswIndex in DocumentChunk Model & Database Indexes

**Files:**
- Modify: `backend/workspaces/models.py:162-190`
- Create: `backend/workspaces/migrations/0013_documentchunk_hnsw_index.py`
- Test: `backend/workspaces/tests/test_pgvector.py`

**Interfaces:**
- Schema: `workspaces_documentchunk` таблиця у Postgres має офіційний Django `HnswIndex`.

- [ ] **Step 1: Update DocumentChunk Meta indexes in models.py**

```python
# In backend/workspaces/models.py
from pgvector.django import HnswIndex

# Inside DocumentChunk.Meta:
indexes = [
    models.Index(fields=['workspace']),
    HnswIndex(
        name='chunk_embedding_hnsw_idx',
        fields=['embedding'],
        m=16,
        ef_construction=64,
        opclasses=['vector_cosine_ops'],
    ),
]
```

- [ ] **Step 2: Generate and adjust Django migration**

Створити міграцію `0013_documentchunk_hnsw_index.py`. Перевірити, що на SQLite міграція не викликає помилок (через умовну перевірку вендора БД або SeparateDatabaseAndState).

- [ ] **Step 3: Run pgvector unit tests**

Run: `backend\.venv\Scripts\python.exe manage.py test workspaces.tests.test_pgvector`
Expected: PASS

- [ ] **Step 4: Commit changes**

```bash
git add backend/workspaces/models.py backend/workspaces/migrations/
git commit -m "feat(workspaces): declare HnswIndex directly in DocumentChunk model"
```

---

### Task 5: Add Performance Indexes to WorkspaceChatLog

**Files:**
- Modify: `backend/chats/models.py:36-69`
- Create: `backend/chats/migrations/0002_workspacechatlog_analytics_indexes.py`
- Test: `backend/chats/tests/test_views.py`

**Interfaces:**
- Schema: Індекси `(workspace, created_at)` та `(workspace, needs_handoff)`.

- [ ] **Step 1: Update WorkspaceChatLog Meta indexes in chats/models.py**

```python
# In backend/chats/models.py
class Meta:
    ordering = ('-created_at',)
    verbose_name = 'Workspace chat log'
    verbose_name_plural = 'Workspace chat logs'
    indexes = [
        models.Index(fields=['workspace', 'created_at']),
        models.Index(fields=['workspace', 'needs_handoff']),
    ]
```

- [ ] **Step 2: Generate migration**

Створити міграцію `0002_workspacechatlog_analytics_indexes.py`.

- [ ] **Step 3: Run chats tests**

Run: `backend\.venv\Scripts\python.exe manage.py test chats.tests`
Expected: PASS

- [ ] **Step 4: Commit changes**

```bash
git add backend/chats/models.py backend/chats/migrations/
git commit -m "perf(chats): add analytics query indexes to WorkspaceChatLog"
```

---

## Plan Self-Review Checklist

- [x] **Spec coverage**: Покриває всі вимоги Фази 1 (бекап медіа + БД, HNSW індекси, індекси логів).
- [x] **Placeholder scan**: Немає TBD або нереалізованих заглушок. Всі методи, шляхи та сигнатури чітко визначені.
- [x] **Type consistency**: Використовуються точні назви полів моделей (`needs_handoff`, `workspace`, `embedding`).
