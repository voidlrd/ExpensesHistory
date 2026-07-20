CREATE TABLE payment_type (
	id INT PRIMARY KEY IDENTITY(1,1),
	type VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE currency (
	code VARCHAR(3) PRIMARY KEY
);

CREATE TABLE counterparty_category (
	id INT PRIMARY KEY IDENTITY(1,1),
	name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE counterparty (
	id INT PRIMARY KEY IDENTITY(1,1),
	name VARCHAR(250) NOT NULL,
	category INT NOT NULL,
	
	CONSTRAINT fk_counterparty_category FOREIGN KEY (category) REFERENCES counterparty_category(id)
);

CREATE TABLE transaction_record (
	id INT PRIMARY KEY IDENTITY(1,1),
	number INT UNIQUE,
	payment_type INT NOT NULL,
	counterparty INT NOT NULL,
	date DATE,
	
	CONSTRAINT fk_transaction_paymenttype FOREIGN KEY (payment_type) REFERENCES payment_type(id),
	CONSTRAINT fk_transaction_counterparty FOREIGN KEY (counterparty) REFERENCES counterparty(id)
);

CREATE TABLE item_category (
	id INT PRIMARY KEY IDENTITY(1,1),
	name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE item (
	id INT PRIMARY KEY IDENTITY(1,1),
	transaction_id INT NOT NULL,
	item_name VARCHAR(250) NOT NULL,
	category INT NOT NULL,
	amount INT NOT NULL,
	price DECIMAL(10,2) NOT NULL,
	currency VARCHAR(3) NOT NULL,
	refund BIT NOT NULL DEFAULT 0,
	
	CONSTRAINT fk_item_transaction FOREIGN KEY (transaction_id) REFERENCES transaction_record(id),
	CONSTRAINT fk_item_category FOREIGN KEY (category) REFERENCES item_category(id),
	CONSTRAINT fk_item_currency FOREIGN KEY (currency) REFERENCES currency(code)
);