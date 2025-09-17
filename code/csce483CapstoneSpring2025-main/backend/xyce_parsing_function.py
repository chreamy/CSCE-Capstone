import csv
from typing import List, Tuple, Dict, Any, NamedTuple, Optional


class XyceError(Exception):
    """Custom exception for Xyce-related errors."""

    pass


class NetlistError(Exception):
    """Custom exception for netlist parsing and modification errors."""

    pass


class CurveFitError(Exception):
    """Custom exception for curve fitting related errors"""

    pass


def parse_xyce_prn_output(prn_filepath: str) -> Tuple[List[str], List[List[float]]]:
    """Parses a Xyce .prn output file.

    Args:
        prn_filepath: Path to the .prn file.

    Returns:
        A tuple containing:
          - A list of variable names (strings).
          - A list of data rows (lists of floats).

    Raises:
        XyceError: If the file cannot be opened or parsed.
    """
    try:
        with open(prn_filepath, "r") as csvfile:
            csvreader = csv.reader(csvfile)
            try:
                variable_names = next(csvreader)  # Read header row
                data = []
                for row in csvreader:
                    float_row = []
                    for item in row:
                        try:
                            float_row.append(float(item))
                        except ValueError:
                            # Ignore non-numeric values (like "End of Xyce...")
                            pass
                    if float_row:  # Only add the row if it has some numeric data
                        data.append(float_row)
            except (ValueError, StopIteration) as e:
                raise XyceError(f"Error parsing .prn file: Invalid data format, {e}")

            if not data:  # if there is no data
                raise XyceError(f"No data rows found in the file {prn_filepath}")

        return variable_names, data

    except FileNotFoundError:
        raise XyceError(f".prn file not found: {prn_filepath}")
    except OSError as e:
        raise XyceError(f"Error opening .prn file: {e}")
    except XyceError:  # re-raise custom exception
        raise
    except Exception as e:
        raise XyceError(f"An unexpected error occurred: {e}")
