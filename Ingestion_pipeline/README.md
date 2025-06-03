# Ingestion Pipeline

This directory contains scripts for ingesting, updating, and managing tool and vendor data in the Neo4j graph database for the Unified MCP Tool Graph project.

## Contents

- **Ingestion_Neo4j.py**: Main script for ingesting tools and vendors into Neo4j from a preprocessed JSON file. Sets up all new/updated tools with `disabled: false` by default.
- **disable_tools.py**: Script to instantly disable (quarantine) any set of tools by setting their `disabled` property to `true` in Neo4j. Useful as a "kill switch" for compromised or malicious tools.
- **enable_tools.py**: Script to re-enable (un-quarantine) any set of tools by setting their `disabled` property to `false` in Neo4j.
- **Preprocess_parse_and_embed.py**: Preprocesses and embeds tool data before ingestion.
- **cluster_vendors_ingestion.py**, **cluster_vendors_usecase.py**: Scripts for advanced vendor clustering and use case mapping.

## Usage

### Ingesting Tools and Vendors

```bash
python Ingestion_Neo4j.py
```
This will read from `parsed_tools_with_embeddings.json` and insert/update all tools and vendors in Neo4j. All tools are enabled (`disabled: false`) by default.

### Disabling (Quarantining) Tools

```bash
python disable_tools.py tool_name1 tool_name2 ...
```
This sets `disabled: true` for the specified tools, instantly removing them from all retrieval queries.

### Re-enabling Tools

```bash
python enable_tools.py tool_name1 tool_name2 ...
```
This sets `disabled: false` for the specified tools, making them available for retrieval again.

## Security Kill Switch

The `disabled` property on each `:Tool` node allows for rapid quarantine of any tool without deleting its history. All retrieval queries are designed to ignore tools where `disabled = true`.

---

For more details, see the main project README.
