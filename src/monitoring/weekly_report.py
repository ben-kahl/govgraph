import os
import time
import datetime
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
LOG_GROUP_NAME = os.environ.get("LOG_GROUP_NAME")
REGION = os.environ.get("AWS_REGION", "us-east-1")

logs_client = boto3.client('logs', region_name=REGION)
sns_client = boto3.client('sns', region_name=REGION)

QUERY = """
filter @message like /RESOLVE:/
| filter @message not like /Fuzzy Tier/
| filter @message not like /Fuzzy match result/
| parse @message /RESOLVE:\s+(?<resolution_type>.*?)\s+for/
| stats count(*) as tier_count by resolution_type
| sort tier_count desc
"""

def lambda_handler(event, context):
    logger.info("Starting Weekly Resolution Analytics Report...")
    
    end_time = datetime.datetime.now()
    start_time = end_time - datetime.timedelta(days=7)
    
    start_ts = int(start_time.timestamp())
    end_ts = int(end_time.timestamp())
    
    logger.info(f"Querying logs from {start_time} to {end_time}")
    
    try:
        response = logs_client.start_query(
            logGroupName=LOG_GROUP_NAME,
            startTime=start_ts,
            endTime=end_ts,
            queryString=QUERY
        )
        
        query_id = response['queryId']
        
        status = 'Running'
        while status in ['Running', 'Scheduled']:
            time.sleep(2)
            res = logs_client.get_query_results(queryId=query_id)
            status = res['status']
            
        if status != 'Complete':
            logger.error(f"Query failed with status: {status}")
            return {'statusCode': 500, 'body': f"Query failed: {status}"}
            
        results = res.get('results', [])
        
        if not results:
            message = "No resolution logs found for the past 7 days."
            logger.info(message)
            send_sns_email(message)
            return {'statusCode': 200, 'body': 'No data'}
            
        total_resolutions = 0
        tier_data = []
        
        for row in results:
            tier_dict = {field['field']: field['value'] for field in row}
            resolution_type = tier_dict.get('resolution_type', 'Unknown')
            count = int(tier_dict.get('tier_count', 0))
            
            tier_data.append((resolution_type, count))
            total_resolutions += count
            
        report_lines = [
            "GovGraph Weekly Entity Resolution Report",
            "----------------------------------------",
            f"Total Entities Resolved: {total_resolutions:,}",
            ""
        ]
        
        for r_type, count in tier_data:
            percentage = (count / total_resolutions) * 100 if total_resolutions > 0 else 0
            report_lines.append(f"{r_type.ljust(25)} | {count:>6,} | {percentage:>5.1f}%")
            
        report_lines.append("")
        report_lines.append("To view the interactive pie chart, open AWS CloudWatch Logs Insights and run this query:")
        report_lines.append(f"Log Group: {LOG_GROUP_NAME}")
        report_lines.append("Query:")
        report_lines.append(QUERY.strip())
        
        final_message = "
".join(report_lines)
        logger.info("Report generated successfully.")
        
        send_sns_email(final_message)
        
        return {'statusCode': 200, 'body': 'Report sent successfully'}
        
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        return {'statusCode': 500, 'body': str(e)}

def send_sns_email(message):
    if not SNS_TOPIC_ARN:
        logger.warning("No SNS_TOPIC_ARN configured. Skipping email.")
        return
        
    sns_client.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="GovGraph Weekly Resolution Analytics",
        Message=message
    )
    logger.info("Email published to SNS.")
