-- Smart IT Support Ticket Classifier - MySQL schema
-- Run with:  mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS ticket_classifier;
USE ticket_classifier;

-- One row per support ticket
CREATE TABLE IF NOT EXISTS tickets (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    title              VARCHAR(200)  NOT NULL,
    description        TEXT          NOT NULL,
    requester_email    VARCHAR(150)  NOT NULL,
    category           VARCHAR(50)   NOT NULL,          -- predicted by the ML model (agents can correct it)
    confidence         DECIMAL(5,4)  NOT NULL,          -- model probability, 0 to 1
    priority           ENUM('Low','Medium','High','Critical') NOT NULL DEFAULT 'Medium',
    status             ENUM('Open','In Progress','Resolved','Closed') NOT NULL DEFAULT 'Open',
    assigned_team      VARCHAR(100)  NOT NULL,
    manually_corrected BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at         DATETIME      NOT NULL,          -- set by the API in UTC
    due_at             DATETIME      NOT NULL,          -- SLA deadline: created_at + SLA hours for the priority
    resolved_at        DATETIME      NULL,
    updated_at         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_status   (status),
    INDEX idx_priority (priority),
    INDEX idx_due_at   (due_at)
);

-- Audit trail: every change made to a ticket
CREATE TABLE IF NOT EXISTS ticket_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id   INT          NOT NULL,
    action      VARCHAR(40)  NOT NULL,      -- created, status_changed, priority_changed, category_corrected
    old_value   VARCHAR(100) NULL,
    new_value   VARCHAR(100) NULL,
    changed_at  DATETIME     NOT NULL,
    CONSTRAINT fk_history_ticket FOREIGN KEY (ticket_id)
        REFERENCES tickets(id) ON DELETE CASCADE,
    INDEX idx_history_ticket (ticket_id)
);

-- Example report query: tickets per category with open count and average confidence
-- SELECT category,
--        COUNT(*)                                                        AS total_tickets,
--        SUM(CASE WHEN status IN ('Open','In Progress') THEN 1 ELSE 0 END) AS open_tickets,
--        ROUND(AVG(confidence) * 100, 1)                                 AS avg_confidence_pct
-- FROM tickets
-- GROUP BY category
-- ORDER BY total_tickets DESC;

-- Example JOIN: full change history for one ticket
-- SELECT t.id, t.title, h.action, h.old_value, h.new_value, h.changed_at
-- FROM tickets t
-- JOIN ticket_history h ON h.ticket_id = t.id
-- WHERE t.id = 1
-- ORDER BY h.changed_at;
