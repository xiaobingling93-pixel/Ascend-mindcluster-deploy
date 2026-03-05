#!/usr/bin/env python3
import csv
import subprocess
import sys
import os
import argparse


def get_csv_path_from_input():
    """Get CSV file path interactively"""
    while True:
        csv_path = input("Please enter the absolute path to the CSV file: ").strip()
        if os.path.exists(csv_path):
            return csv_path
        else:
            print(f"Error: File '{csv_path}' does not exist. Please try again.")


def parse_csv_file(csv_path):
    """
    Parse CSV file
    :return: (success, result) where result is either (label_keys, node_data_list) or error message
             label_keys: List of label keys
             node_data_list: Each element is (node_name, labels_dict)
    """
    try:
        with open(csv_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            rows = list(reader)

            if len(rows) < 2:
                return False, "CSV file must contain at least a header row and one data row"

            # First row is header
            header = rows[0]
            if header[0] != "nodeName":
                return False, "First column of CSV file must be 'nodeName'"

            # Extract label keys (starting from second column)
            label_keys = header[1:]
            node_data_list = []

            # Iterate through data rows (starting from second row)
            for row_num, row in enumerate(rows[1:], start=2):
                if len(row) == 0:
                    continue  # Skip empty rows

                node_name = row[0]
                if not node_name:
                    print(f"Warning: Row {row_num} has empty nodeName, skipped")
                    continue

                # Build label dictionary
                labels = {}
                for i, key in enumerate(label_keys):
                    if i + 1 < len(row):
                        value = row[i + 1]
                        labels[key] = value
                    else:
                        labels[key] = ""

                node_data_list.append((node_name, labels))

        return True, (label_keys, node_data_list)

    except FileNotFoundError:
        return False, f"File '{csv_path}' not found"
    except Exception as e:
        return False, f"Error reading CSV file: {e}"


def execute_kubectl_command(action, node_name, labels):
    """
    Execute kubectl label command
    :param action: 'apply' or 'delete'
    :param node_name: Node name
    :param labels: Dictionary with label keys and values (value ignored for delete)
    :return: (success, error_message)
    """
    if action == 'apply':
        cmd = ["kubectl", "label", "nodes", node_name, "--overwrite"]
        for key, value in labels.items():
            if value:  # Ensure value is not empty
                cmd.append(f"{key}={value}")
    elif action == 'delete':
        cmd = ["kubectl", "label", "nodes", node_name]
        for key in labels.keys():
            cmd.append(f"{key}-")
    else:
        return False, f"Unknown action type: {action}"

    if len(cmd) <= 4:  # No label operations, skip
        return True, None

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, None
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return False, error_msg
    except subprocess.TimeoutExpired:
        return False, "Command execution timeout"
    except Exception as e:
        return False, str(e)


def process_labels(action, csv_path):
    """Process label addition or removal
    :return: (success, result) where result is either (successful_nodes, failed_nodes) or error message
    """
    # Parse CSV file
    parse_success, parse_result = parse_csv_file(csv_path)
    if not parse_success:
        return False, parse_result

    label_keys, node_data_list = parse_result

    if not node_data_list:
        return True, ([], [])  # No valid data rows, but not an error

    # Initialize success and failure lists
    successful_nodes = []
    failed_nodes = []  # Each element is (node_name, error_message)

    # Iterate through nodes and execute operations
    for node_name, labels in node_data_list:
        success, error_msg = execute_kubectl_command(action, node_name, labels)
        if success:
            successful_nodes.append(node_name)
        else:
            failed_nodes.append((node_name, error_msg))

    return True, (successful_nodes, failed_nodes)


def main():
    parser = argparse.ArgumentParser(
        description='Add or remove labels for Kubernetes nodes based on CSV file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s apply --config-path /path/to/labels.csv
  %(prog)s delete --config-path /path/to/labels.csv
  %(prog)s apply  # Without --config-path, will enter interactive mode
        """
    )

    # Create subcommand parsers
    subparsers = parser.add_subparsers(dest='command', help='Available commands', required=True)

    # apply command
    apply_parser = subparsers.add_parser('apply', help='Add labels to nodes')
    apply_parser.add_argument('--config-path', help='Absolute path to CSV file')

    # delete command
    delete_parser = subparsers.add_parser('delete', help='Remove labels from nodes')
    delete_parser.add_argument('--config-path', help='Absolute path to CSV file')

    args = parser.parse_args()

    # Get CSV file path
    if args.config_path:
        csv_path = args.config_path
    else:
        csv_path = get_csv_path_from_input()

    # Verify file exists
    if not os.path.exists(csv_path):
        print(f"Error: File '{csv_path}' does not exist")
        sys.exit(1)

    action_display = "Adding" if args.command == 'apply' else "Removing"
    print(f"Starting {action_display.lower()} labels...")

    # Process label operations
    success, result = process_labels(args.command, csv_path)

    if not success:
        print(f"Error: {result}")
        sys.exit(1)

    successful_nodes, failed_nodes = result

    # Output results
    if not failed_nodes:
        if successful_nodes:
            print(f"{action_display} labels completed successfully!")
            print(f"Processed {len(successful_nodes)} nodes.")
        else:
            print("No valid nodes to process.")
    else:
        print(f"{action_display} labels completed, but some nodes failed.")
        if successful_nodes:
            print(f"Successful nodes ({len(successful_nodes)}): {', '.join(successful_nodes)}")
        else:
            print("No successful nodes.")

        print(f"Failed nodes ({len(failed_nodes)}) and error messages:")
        for node_name, error_msg in failed_nodes:
            print(f"  - {node_name}: {error_msg}")

        # Exit with error code if any nodes failed
        sys.exit(1)


if __name__ == "__main__":
    main()