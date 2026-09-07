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

CREATE TABLE counterparty_location (
	id INT PRIMARY KEY IDENTITY(1,1),
	counterparty_id INT NOT NULL,
	label VARCHAR(100),

	CONSTRAINT fk_location_counterparty FOREIGN KEY (counterparty_id) REFERENCES counterparty(id),
	CONSTRAINT uq_location_counterparty UNIQUE (counterparty_id, label)
);

CREATE TABLE transaction_record (
	id INT PRIMARY KEY IDENTITY(1,1),
	number VARCHAR(50) UNIQUE,
	payment_type INT NOT NULL,
	currency VARCHAR(3) NOT NULL,
	counterparty INT NOT NULL,
	location INT,
	date DATE NOT NULL,
	total_amount DECIMAL(10,2),
	
	CONSTRAINT fk_transaction_paymenttype FOREIGN KEY (payment_type) REFERENCES payment_type(id),
	CONSTRAINT fk_transaction_counterparty FOREIGN KEY (counterparty) REFERENCES counterparty(id),
	CONSTRAINT fk_transaction_currency FOREIGN KEY (currency) REFERENCES currency(code),
	CONSTRAINT fk_transaction_location FOREIGN KEY (location) REFERENCES counterparty_location(id)
);

CREATE TABLE item_category (
	id INT PRIMARY KEY IDENTITY(1,1),
	name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE product (
	id INT PRIMARY KEY IDENTITY(1,1),
	name VARCHAR(250) NOT NULL,
	brand VARCHAR(100),
	unit_of_measure VARCHAR(20),
	category INT,

	CONSTRAINT fk_product_category FOREIGN KEY (category) REFERENCES item_category(id)
);

CREATE TABLE item (
	id INT PRIMARY KEY IDENTITY(1,1),
	transaction_id INT NOT NULL,
	product_id INT NOT NULL,
	item_name_override VARCHAR(250),
	amount DECIMAL(10,3) NOT NULL,
	price DECIMAL(10,2) NOT NULL,
	discount DECIMAL(10,2) NOT NULL DEFAULT 0,
	refund BIT NOT NULL DEFAULT 0,
	
	CONSTRAINT fk_item_transaction FOREIGN KEY (transaction_id) REFERENCES transaction_record(id),
	CONSTRAINT fk_item_product FOREIGN KEY (product_id) REFERENCES product(id)
);

CREATE TABLE income_record (
	id INT PRIMARY KEY IDENTITY(1,1),
	counterparty INT NOT NULL,
	date DATE NOT NULL,
	currency VARCHAR(3) NOT NULL,
	net_amount DECIMAL(10,2) NOT NULL,
	payment_type INT NOT NULL,

	CONSTRAINT fk_income_counterparty FOREIGN KEY (counterparty) REFERENCES counterparty(id),
	CONSTRAINT fk_income_currency FOREIGN KEY (currency) REFERENCES currency(code),
	CONSTRAINT fk_income_paymenttype FOREIGN KEY (payment_type) REFERENCES payment_type(id)
);