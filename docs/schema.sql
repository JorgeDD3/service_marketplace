-- ServiceSphere schema.sql (SQLite)
-- Generated from: sqlite3 instance/site.db ".schema"
-- This file is a snapshot; the source of truth is app/models.py

CREATE TABLE roles (
	id INTEGER NOT NULL, 
	role_name VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (role_name)
);
CREATE TABLE users (
	id INTEGER NOT NULL, 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role_id INTEGER, 
	is_active BOOLEAN NOT NULL, 
	disabled_at DATETIME, 
	disabled_reason TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
);
CREATE TABLE password_reset_tokens (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	used_at DATETIME, 
	request_ip VARCHAR(45), 
	user_agent VARCHAR(255), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);
CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);
CREATE INDEX ix_password_reset_tokens_expires_at ON password_reset_tokens (expires_at);
CREATE TABLE provider_profiles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	bio TEXT, 
	hourly_rate FLOAT, 
	availability_notes TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE service_requests (
	id INTEGER NOT NULL, 
	client_id INTEGER NOT NULL, 
	subject VARCHAR(150) NOT NULL, 
	description TEXT NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	claimed_by_provider_id INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	closed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(client_id) REFERENCES users (id), 
	FOREIGN KEY(claimed_by_provider_id) REFERENCES users (id)
);
CREATE TABLE provider_availability (
	id INTEGER NOT NULL, 
	provider_profile_id INTEGER NOT NULL, 
	day_of_week INTEGER NOT NULL, 
	start_time VARCHAR(5) NOT NULL, 
	end_time VARCHAR(5) NOT NULL, 
	slot_minutes INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(provider_profile_id) REFERENCES provider_profiles (id)
);
CREATE TABLE provider_time_off (
	id INTEGER NOT NULL, 
	provider_profile_id INTEGER NOT NULL, 
	start_datetime DATETIME NOT NULL, 
	end_datetime DATETIME NOT NULL, 
	all_day BOOLEAN NOT NULL, 
	reason TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(provider_profile_id) REFERENCES provider_profiles (id)
);
CREATE TABLE provider_verifications (
	id INTEGER NOT NULL, 
	provider_profile_id INTEGER NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	legal_name VARCHAR(120), 
	license_number VARCHAR(80), 
	portfolio_url VARCHAR(255), 
	id_document_filename VARCHAR(255), 
	certification_filename VARCHAR(255), 
	submitted_at DATETIME, 
	reviewed_at DATETIME, 
	reviewed_by_admin_id INTEGER, 
	admin_notes TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(provider_profile_id) REFERENCES provider_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(reviewed_by_admin_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX ix_provider_verifications_status ON provider_verifications (status);
CREATE UNIQUE INDEX ix_provider_verifications_provider_profile_id ON provider_verifications (provider_profile_id);
CREATE INDEX ix_provider_verifications_reviewed_by_admin_id ON provider_verifications (reviewed_by_admin_id);
CREATE TABLE services (
	id INTEGER NOT NULL, 
	provider_profile_id INTEGER NOT NULL, 
	title VARCHAR(150) NOT NULL, 
	category VARCHAR(100), 
	description TEXT, 
	price FLOAT, 
	duration_minutes INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	moderation_note TEXT, 
	moderated_at DATETIME, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(provider_profile_id) REFERENCES provider_profiles (id)
);
CREATE TABLE bookings (
	id INTEGER NOT NULL, 
	provider_id INTEGER NOT NULL, 
	client_id INTEGER NOT NULL, 
	service_id INTEGER NOT NULL, 
	booking_datetime DATETIME NOT NULL, 
	duration_minutes INTEGER NOT NULL, 
	status VARCHAR(50), 
	decided_at DATETIME, 
	provider_note TEXT, 
	admin_note TEXT, 
	admin_action_at DATETIME, 
	created_at DATETIME, payment_status VARCHAR(32) NOT NULL DEFAULT 'unpaid', paid_at DATETIME, payment_reference VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(provider_id) REFERENCES users (id), 
	FOREIGN KEY(client_id) REFERENCES users (id), 
	FOREIGN KEY(service_id) REFERENCES services (id)
);
CREATE TABLE conversations (
	id INTEGER NOT NULL, 
	booking_id INTEGER NOT NULL, 
	client_id INTEGER NOT NULL, 
	provider_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (booking_id), 
	FOREIGN KEY(booking_id) REFERENCES bookings (id), 
	FOREIGN KEY(client_id) REFERENCES users (id), 
	FOREIGN KEY(provider_id) REFERENCES users (id)
);
CREATE INDEX ix_conversations_client_id ON conversations (client_id);
CREATE INDEX ix_conversations_provider_id ON conversations (provider_id);
CREATE TABLE messages (
	id INTEGER NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	sender_id INTEGER NOT NULL, 
	body TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id), 
	FOREIGN KEY(sender_id) REFERENCES users (id)
);
CREATE INDEX ix_messages_sender_id ON messages (sender_id);
CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);
CREATE TABLE conversation_reads (
	id INTEGER NOT NULL, 
	conversation_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	last_read_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_conversation_reads_conversation_user UNIQUE (conversation_id, user_id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_conversation_reads_conversation_id ON conversation_reads (conversation_id);
CREATE INDEX ix_conversation_reads_user_id ON conversation_reads (user_id);
