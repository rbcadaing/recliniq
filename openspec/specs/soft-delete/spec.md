# soft-delete Specification

## Purpose

Guarantees that RecliniQ records are never physically removed. Deleting a record marks it as deleted with who and when, hides it from normal reads, and keeps it restorable and auditable.

## Requirements

### Requirement: Soft-delete columns on every table
Every application table SHALL have a nullable `deleted_at` timestamp (with time zone) and a nullable `deleted_by` actor identifier. The only tables without them SHALL be those on an explicit, documented exemption list, which starts empty. Migration bookkeeping tables are not application tables.

#### Scenario: New table without soft-delete columns
- **WHEN** a developer adds an application table that lacks `deleted_at` or `deleted_by` and is not on the exemption list
- **THEN** the automated test suite fails and names the table

#### Scenario: Active record
- **WHEN** a record is created
- **THEN** its `deleted_at` and `deleted_by` are both null

### Requirement: Deleting marks the record instead of removing it
Deleting a record SHALL set `deleted_at` to the current time and `deleted_by` to the acting user's identifier, or leave `deleted_by` null when the actor is the system. The row SHALL remain in the database. Deleting a record that is already deleted SHALL leave its original `deleted_at` and `deleted_by` unchanged.

#### Scenario: Soft delete by a user
- **WHEN** a user deletes a record
- **THEN** the row still exists, `deleted_at` holds the deletion time, and `deleted_by` holds that user's identifier

#### Scenario: Deleting an already-deleted record
- **WHEN** a record that was already deleted is deleted again by a different actor
- **THEN** its `deleted_at` and `deleted_by` keep their original values

### Requirement: Deleted records are excluded by default
All reads of soft-deletable records SHALL exclude deleted records unless the caller explicitly asks to include them. This covers lookups by identifier, lists, filters, joins, and records loaded through relationships.

#### Scenario: Lookup of a deleted record
- **WHEN** code looks up a deleted record by its identifier without asking to include deleted records
- **THEN** no record is returned

#### Scenario: List excludes deleted records
- **WHEN** code lists records of a type where some are deleted
- **THEN** only records that are not deleted are returned

#### Scenario: Related records exclude deleted children
- **WHEN** a parent record is loaded together with its related child records and some children are deleted
- **THEN** the deleted children are not included

### Requirement: Explicit access to deleted records
Code SHALL be able to explicitly request deleted records, either alone or together with active ones, so they can be listed for review and restored.

#### Scenario: List only deleted records
- **WHEN** code explicitly requests the deleted records of a type
- **THEN** only deleted records are returned, each with its `deleted_at` and `deleted_by`

#### Scenario: Include deleted records
- **WHEN** code looks up a deleted record by identifier and explicitly asks to include deleted records
- **THEN** the record is returned

### Requirement: Restoring a deleted record
Restoring a deleted record SHALL clear its `deleted_at` and `deleted_by`, making it visible to default reads again. Restoring a record that is not deleted SHALL change nothing.

#### Scenario: Restore
- **WHEN** a deleted record is restored
- **THEN** its `deleted_at` and `deleted_by` are null and default reads return it again

#### Scenario: Restore an active record
- **WHEN** a record that is not deleted is restored
- **THEN** the record is unchanged

### Requirement: Application rejects hard deletes
The backend SHALL refuse to physically delete a soft-deletable record through the ORM, whether one entity at a time or as a bulk delete statement. The attempt SHALL fail with an error before any SQL `DELETE` is sent. API callers SHALL see a 500 response in the standard error envelope, because a hard-delete attempt is a programming defect, not a user error.

#### Scenario: Deleting an entity through the session
- **WHEN** code marks a soft-deletable entity for physical deletion and the unit of work is flushed
- **THEN** an error is raised, the transaction is rolled back, and the row is unchanged

#### Scenario: Bulk delete statement
- **WHEN** code executes a bulk delete statement against a soft-deletable model
- **THEN** an error is raised and no rows are deleted

### Requirement: Database rejects hard deletes
Every soft-deletable table SHALL be protected in the database itself, so that a `DELETE` against it fails even when issued as raw SQL. The only exception is an explicit, transaction-scoped maintenance override that application code never sets.

#### Scenario: Raw SQL delete
- **WHEN** a raw SQL `DELETE` is executed against a soft-deletable table
- **THEN** the database raises an error and no rows are deleted

#### Scenario: Unprotected table
- **WHEN** a soft-deletable table exists in the migrated database without the delete protection
- **THEN** the automated test suite fails and names the table

#### Scenario: Maintenance override
- **WHEN** an operator explicitly enables the maintenance override for the current transaction and issues a `DELETE`
- **THEN** the delete succeeds for that transaction only

### Requirement: Uniqueness ignores deleted records
Uniqueness rules on soft-deletable tables SHALL apply only among records that are not deleted, so a deleted record never blocks a new record with the same unique values.

#### Scenario: Re-create after delete
- **WHEN** a record with a unique value is deleted and a new record with the same value is created
- **THEN** the new record is accepted

#### Scenario: Duplicate among active records
- **WHEN** a record is created with a unique value already used by a record that is not deleted
- **THEN** the creation is rejected as a conflict

### Requirement: No automatic cascading of soft deletes
Soft-deleting a record SHALL NOT automatically soft-delete related records. Any cascade SHALL be performed explicitly by the feature that owns the records.

#### Scenario: Parent deleted
- **WHEN** a parent record with related child records is soft-deleted
- **THEN** the child records' `deleted_at` and `deleted_by` are unchanged
