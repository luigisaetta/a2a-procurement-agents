# Procurement Data MCP Server

This service exposes read-only procurement master data through MCP tools.

It uses FastMCP and reads from the MySQL `procurement_demo` schema created by the Docker Compose deployment.

## Environment

Use the repository conda environment:

```bash
conda activate a2a-procurement-agents
```

Required variables:

```bash
cp services/procurement-data-mcp/.env.example services/procurement-data-mcp/.env
export PROCUREMENT_DB_HOST=127.0.0.1
export PROCUREMENT_DB_PORT=3306
export PROCUREMENT_DB_NAME=procurement_demo
export PROCUREMENT_DB_USER=procurement_app
export PROCUREMENT_DB_PASSWORD=procurement_app_password
```

## Start MySQL

```bash
cd deployments/docker-compose
docker compose up -d mysql
```

## Run The MCP Server

Run from the repository root:

```bash
PYTHONPATH=services/procurement-data-mcp/src \
conda run -n a2a-procurement-agents \
python -m procurement_data_mcp.server --host 127.0.0.1 --port 8011 --path /mcp
```

The server always uses MCP streamable HTTP transport. The local endpoint is:

```text
http://127.0.0.1:8011/mcp
```

## Tools

- `list_plants`
- `get_plant`
- `list_parts`
- `get_part`
- `list_suppliers`
- `get_supplier`
- `list_suppliers_for_part`
- `list_parts_for_supplier`
- `find_suppliers_for_part`
