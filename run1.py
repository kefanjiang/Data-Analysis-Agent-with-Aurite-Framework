from dotenv import load_dotenv
import asyncio
import logging
import json
from termcolor import colored
from aurite import Aurite
from aurite.config.config_models import AgentConfig, LLMConfig,ClientConfig,WorkflowConfig
import pandas as pd


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():

    load_dotenv()

    aurite = Aurite()

    try:
        await aurite.initialize()
        #---LLM---
        llm_config = LLMConfig(
            llm_id="gpt4_turbo",
            provider="openai",
            model_name="gpt-4-turbo-preview",
            max_tokens=1000

        )

        await aurite.register_llm_config(llm_config)

        
        #---mcp server---
        
        mcp_server_config = ClientConfig(
             name="news_searching",
             http_endpoint="https://server.smithery.ai/exa/mcp?api_key={SMITHERY_API_KEY}&profile={SMITHERY_PROFILE_ID}",
             capabilities=['tools'],

        )
        await aurite.register_client(mcp_server_config)
        

        database_mcp_config = ClientConfig(
            name ="database_mcp",
            http_endpoint="https://server.smithery.ai/@supabase-community/supabase-mcp/mcp?api_key={SMITHERY_API_KEY}&profile={SMITHERY_PROFILE_ID}",
            capabilities=["tools"]
        )
        await aurite.register_client(database_mcp_config)
        
    

        visualization_mcp_config = ClientConfig(
            name="visualization_mcp",
            http_endpoint="https://server.smithery.ai/@antvis/mcp-server-chart/mcp?api_key={SMITHERY_API_KEY}&profile={SMITHERY_PROFILE_ID}",
            capabilities=['tools'],
        
        )
        await aurite.register_client(visualization_mcp_config)


        #---json schema----
        news_search_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "format": "uri",  # Added format validation
                        "description": "The URL of the news article"
                    },
                    "summary": {
                        "type": "string",
                        "minLength": 10,  # Ensure summaries aren't empty
                        "maxLength": 500,  # Prevent overly long summaries
                        "description": "A concise summary of the article"
                    }
                },
                "required": ["url", "summary"],
                "additionalProperties": False  # Prevent extra fields
            },
            "minItems": 5,
            "maxItems": 5,
            "description": "Array of exactly 5 news items"
        }

        table_json_schema={
        
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Dynamic Table Schema",
        "description": "A flexible schema for tables with any number of columns and rows",
        "type": "object",
        "properties": {
            "metadata": {
            "type": "object",
            "properties": {
                "tableName": {
                "type": "string",
                "description": "Optional name for the table"
                },
                "description": {
                "type": "string",
                "description": "Optional description of the table"
                },
                "columnCount": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of columns in the table"
                },
                "rowCount": {
                "type": "integer",
                "minimum": 0,
                "description": "Number of rows in the table"
                },
                "createdAt": {
                "type": "string",
                "format": "date-time",
                "description": "Timestamp when table was created"
                }
            },
            "additionalProperties": True
            },
            "columns": {
            "type": "array",
            "description": "Array of column definitions",
            "items": {
                "type": "object",
                "properties": {
                "id": {
                    "type": "string",
                    "description": "Unique identifier for the column"
                },
                "name": {
                    "type": "string",
                    "description": "Display name of the column"
                },
                "type": {
                    "type": "string",
                    "enum": ["string", "number", "boolean", "date", "datetime", "object", "array", "null"],
                    "description": "Data type of the column"
                },
                "required": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether this column is required"
                },
                "defaultValue": {
                    "description": "Default value for this column"
                },
                "constraints": {
                    "type": "object",
                    "properties": {
                    "minLength": {"type": "integer", "minimum": 0},
                    "maxLength": {"type": "integer", "minimum": 0},
                    "minimum": {"type": "number"},
                    "maximum": {"type": "number"},
                    "pattern": {"type": "string", "format": "regex"},
                    "enum": {"type": "array", "items": {}}
                    },
                    "additionalProperties": True
                }
                },
                "required": ["id", "name", "type"],
                "additionalProperties": True
            }
            },
            "rows": {
            "type": "array",
            "description": "Array of row data",
            "items": {
                "type": "object",
                "description": "Row data as key-value pairs where keys correspond to column IDs",
                "patternProperties": {
                ".*": {
                    "description": "Cell value - can be any type based on column definition"
                }
                },
                "additionalProperties": True
            }
            },

        },
        "required": ["rows"],
        "additionalProperties": True,
        
        "examples": [
            {
            "rows": [
                {"id": 1, "name": "John Doe", "email": "john@example.com"},
                {"id": 2, "name": "Jane Smith", "email": "jane@example.com"}
            ]
            },
            {
            "metadata": {
                "tableName": "Products"
            },
            "rows": [
                {"sku": "ABC123", "price": 29.99, "available": True},
                {"sku": "XYZ789", "price": 49.99, "available": False}
            ]
            }
        ]
        }
            
        

        

        #---agent---
        news_agent_config = AgentConfig(
            name="news_agent",
            system_prompt="""You are a news research assistant. Your task is to search for news and provide diverse, informative summaries.

IMPORTANT: Your final output MUST be a JSON array containing exactly 5 news items, formatted as:
[
  {
    "url": "https://example.com/article1",
    "summary": "Brief summary of the article"
  },
  {
    "url": "https://example.com/article2",
    "summary": "Brief summary of the article"
  },
  ... (3 more items)
]

Instructions:
1. IMPORTANT: You MUST perform AT LEAST 3 DIFFERENT SEARCHES using web_search_exa:
   - Search 1: Use the user's exact query
   - Search 2: Add "market share comparison" or "vs competitors" to the query
   - Search 3: Add "regional analysis" or "forecast 2025" to the query
   - Optional: More searches with terms like "profit margins", "supply chain", "consumer trends"
   - DO NOT proceed to crawling until you've done multiple searches
2. After completing multiple searches, review ALL results and select the 5 most diverse articles covering different aspects
   - Avoid repeating the same information across summaries
   - Highlight what makes each article's perspective or data unique
   - Include specific numbers, dates, percentages, or other concrete details when available
4. Keep summaries under 500 characters each
5. Return ONLY the JSON array with exactly 5 news items - no additional text or formatting

Do not include the schema definition in your output, only the actual data array.""",
            mcp_servers=["news_searching"],
            include_history=False,
            config_validation_schema=news_search_schema,
            llm_config_id="gpt4_turbo"
        )

        await aurite.register_agent(news_agent_config)

        database_agent_config = AgentConfig(
            name="database_agent",
            system_prompt="""You are a professional database manager.

Your responsibilities:
1. Understand the user's query and translate it to appropriate SQL
2. Use the execute_sql tool for data minipulation language. For example, SELECT/INSERT/UPDATE/DELETE
3. Use the apply_migration tool for data definition language. For example, CREATE/DROP/ALTER TABLE use apply_migration
4. Format results in a clear, readable table format


Guidelines:
- Always validate SQL syntax before execution
- For SELECT queries, only display exact columns that required by user, present results in table as json format
- For INSERT/UPDATE/DELETE, confirm the number of affected rows
- Handle errors gracefully and explain issues to the user""",
            mcp_servers=["database_mcp"],
            llm_config_id="gpt4_turbo",
            config_validation_schema=table_json_schema
        )
        await aurite.register_agent(database_agent_config)


        visualization_agent_config = AgentConfig(
            name= "visualization_agent",
            system_prompt="""You are good at visualization of data. The user would tell you 
             what kind of data they want to visualize. You should follow the rules below.
             1. If user specify exact kind of chart, you should follow user's requirement.
               If you can't generate the chart provided by user, you should explain the reason. 
             2. If user doesn't specify which chart they want to use, you should analyze which chart
             is the best to display the data.
              
            """,
            mcp_servers=["visualization_mcp"],
            llm_config_id="gpt4_turbo",

        )

        await aurite.register_agent(visualization_agent_config)
       

        user_query = "What is the market size of smartphone in the US. what's the top three brand of smartphone in 2024."
        user_query1 = '''
        project ID:khawkqrnskfmzznfvfef; 
        SELECT "Store", "Dept", SUM("WeeklySales") AS "MonthSales", "Year", "Month"
        FROM sales
        WHERE
            "Store" = 1
            AND "Dept" = 1
            AND "Year" = 2020
            AND "Month" IN (1, 2, 3, 4, 5, 6)
        GROUP BY "Store", "Dept", "Year", "Month";

        

        '''
       
        user_query2='''"rows": [
    {
      "Store": 1,
      "Dept": 1,
      "MonthSales": 69146.59,
      "Year": 2020,
      "Month": 1
    },
    {
      "Store": 1,
      "Dept": 1,
      "MonthSales": 125762.63,
      "Year": 2020,
      "Month": 2
    },
    {
      "Store": 1,
      "Dept": 1,
      "MonthSales": 82823.34,
      "Year": 2020,
      "Month": 3
    },
    {
      "Store": 1,
      "Dept": 1,
      "MonthSales": 165056.95,
      "Year": 2020,
      "Month": 4
    },
    {
      "Store": 1,
      "Dept": 1,
      "MonthSales": 68251.72,
      "Year": 2020,
      "Month": 5
    },
    {
      "Store": 1,
      "Dept": 1,
      "MonthSales": 62978.57,
      "Year": 2020,
      "Month": 6
    }
  ]
        draw a column chart and a line chart, y-axis is
        MonthlySales and x-axis is month;
        '''
        
        
        agent_result = await aurite.run_agent(
            agent_name="visualization_agent",
            user_message=user_query2
        )
        
        print(colored("\n--- Agent Result ---", "yellow", attrs=["bold"]))

        if agent_result and hasattr(agent_result, 'primary_text'):
            response_text = agent_result.primary_text
            print(colored(f"Agent's response: {response_text}", "cyan", attrs=["bold"]))
            # for database_agent to output pandas DataFrame
            try:
                print(colored("\n--- DataFrame ---", "green", attrs=["bold"]))
                data = json.loads(response_text) 
                df = pd.DataFrame(data["rows"])
                print(df)
            except json.JSONDecodeError:
                print(colored("Failed to parse response as JSON", "red"))
            # If you want to parse and display the news items nicely:
            try:
                news_items = json.loads(response_text)
                print(colored("\n--- Parsed News Items ---", "green", attrs=["bold"]))
                for i, item in enumerate(news_items, 1):
                    print(colored(f"\n{i}. {item['url']}", "blue"))
                    print(colored(f"   {item['summary']}", "white"))
            except json.JSONDecodeError:
                print(colored("Failed to parse response as JSON", "red"))
        else:
            print(colored("No valid response received from agent", "red"))

    except Exception as e:
        logger.error(f"An error occurred during agent execution: {e}", exc_info=True)
        await aurite.shutdown()
        logger.info("Aurite shutdown complete.")

if __name__ == "__main__":
    # Run the asynchronous main function.
    asyncio.run(main())
