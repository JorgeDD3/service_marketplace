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
	created_at DATETIME, is_active INTEGER DEFAULT 1, disabled_at DATETIME, disabled_reason TEXT, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	FOREIGN KEY(role_id) REFERENCES roles (id)
);
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
	description TEXT, 
	status VARCHAR(50), 
	created_at DATETIME, claimed_by_provider_id INTEGER, updated_at DATETIME, closed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(client_id) REFERENCES users (id)
);
CREATE TABLE services (
	id INTEGER NOT NULL, 
	provider_profile_id INTEGER NOT NULL, 
	title VARCHAR(150) NOT NULL, 
	description TEXT, 
	price FLOAT, 
	created_at DATETIME, is_active INTEGER DEFAULT 1, moderation_note TEXT, moderated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(provider_profile_id) REFERENCES provider_profiles (id)
);
CREATE TABLE bookings (
	id INTEGER NOT NULL, 
	provider_id INTEGER NOT NULL, 
	client_id INTEGER NOT NULL, 
	service_id INTEGER NOT NULL, 
	booking_datetime DATETIME NOT NULL, 
	status VARCHAR(50), 
	created_at DATETIME, 
	provider_note TEXT, 
	decided_at DATETIME, 
	admin_note TEXT, 
	admin_action_at DATETIME, 
	duration_minutes INTEGER DEFAULT 60, 

	-- Demo checkout / payment tracking (Beyond MVP)
	payment_status VARCHAR(32) NOT NULL DEFAULT 'unpaid',
	paid_at DATETIME,
	payment_reference VARCHAR(64),

	PRIMARY KEY (id), 
	FOREIGN KEY(provider_id) REFERENCES users (id), 
	FOREIGN KEY(client_id) REFERENCES users (id), 
	FOREIGN KEY(service_id) REFERENCES services (id)
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
-- In-app messaging tied to bookings (Beyond MVP)

CREATE TABLE conversations (
	id INTEGER NOT NULL,
	booking_id INTEGER NOT NULL UNIQUE,
	client_id INTEGER NOT NULL,
	provider_id INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(booking_id) REFERENCES bookings (id),
	FOREIGN KEY(client_id) REFERENCES users (id),
	FOREIGN KEY(provider_id) REFERENCES users (id)
);

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

CREATE TABLE conversation_reads (
	id INTEGER NOT NULL,
	conversation_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	last_read_at DATETIME,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(conversation_id) REFERENCES conversations (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	CONSTRAINT uq_conversation_reads_conversation_user UNIQUE (conversation_id, user_id)
);
