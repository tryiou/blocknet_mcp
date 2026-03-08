"""
Generic Markdown API Documentation Parser

Parses Blocknet-style markdown API documentation to extract:
- Endpoint definitions
- Parameter specifications
- Descriptions and help text

Designed to be generic and work with any Blocknet API doc format.
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParamSpec:
    """Represents a parameter from API documentation"""

    name: str
    param_type: str
    required: bool = True
    description: str = ""
    default_value: str | None = None
    default_description: str | None = None

    @property
    def python_type(self) -> str:
        """Convert API type to Python type"""
        type_map = {
            "string": "str",
            "string(float)": "str",
            "int": "int",
            "bool": "bool",
            "array": "list",
            "object": "dict",
            "float": "float",
            "float64": "float",
            "int64": "int",
        }
        return type_map.get(self.param_type.lower(), "str")

    @property
    def python_default(self) -> str | None:
        """Get Python default value as a literal string"""
        if self.default_value:
            return self.default_value
        if not self.required:
            return "None"
        return None


@dataclass
class EndpointSpec:
    """Represents an API endpoint from documentation"""

    rpc_method: str
    tool_name: str
    description: str = ""
    params: list[ParamSpec] = field(default_factory=list)
    response_type: str = "dict"
    notes: list[str] = field(default_factory=list)
    sample_request: str = ""
    sample_response: str = ""
    error_codes: list[int] = field(default_factory=list)

    @property
    def required_params(self) -> list[ParamSpec]:
        return [p for p in self.params if p.required]

    @property
    def optional_params(self) -> list[ParamSpec]:
        return [p for p in self.params if not p.required]


@dataclass
class ApiSpec:
    """Complete API specification from documentation"""

    name: str = ""
    endpoints: dict[str, EndpointSpec] = field(default_factory=dict)
    error_codes: dict[int, str] = field(default_factory=dict)


class MarkdownParser:
    """Generic parser for Blocknet-style markdown API docs"""

    def __init__(self, doc_path: str, rpc_prefix: str):
        self.doc_path = Path(doc_path)
        self.rpc_prefix = rpc_prefix.lower()
        self.content = ""

    def load(self) -> None:
        """Load the documentation file"""
        with open(self.doc_path, encoding="utf-8") as f:
            self.content = f.read()
        # Remove HTML comments (<!-- ... -->) as they contain disabled endpoints
        self.content = re.sub(r"<!--.*?-->", "", self.content, flags=re.DOTALL)

    def parse(self) -> ApiSpec:
        """Parse the documentation and return API spec"""
        spec = ApiSpec()

        # Extract API name from file
        spec.error_codes = self._parse_error_codes()

        # Parse all endpoints
        endpoint_sections = self._extract_endpoint_sections()

        for section in endpoint_sections:
            endpoint = self._parse_endpoint(section)
            if endpoint:
                spec.endpoints[endpoint.rpc_method] = endpoint

        return spec

    def _extract_endpoint_sections(self) -> list[str]:
        """Extract individual endpoint sections from the markdown"""
        # Use dict to keep last (most complete) occurrence of duplicate headings
        sections_dict = {}

        # Find all ## headers that are API endpoints (dx, xr, etc.)
        # Look for ## followed by API method name at start of line (not in code blocks)
        pattern = rf"## ({self.rpc_prefix}\w+)\s*\n(.*?)(?=## {self.rpc_prefix}\w+|## Status|## Error|\Z)"
        matches = re.finditer(pattern, self.content, re.DOTALL | re.IGNORECASE)

        for match in matches:
            rpc_method = match.group(1)
            # Overwrite earlier sections - keep last (most complete) version
            sections_dict[rpc_method] = f"## {rpc_method}\n{match.group(2)}"

        return list(sections_dict.values())

    def _is_endpoint_header(self, name: str) -> bool:
        """Check if header is an endpoint (not a section header)"""
        return name.lower().startswith(self.rpc_prefix)

    def _parse_endpoint(self, section: str) -> EndpointSpec | None:
        """Parse a single endpoint section"""
        # Extract RPC method name from header
        header_match = re.search(r"## (\w+)\s*\n", section)
        if not header_match:
            return None

        rpc_method = header_match.group(1)

        # Convert to tool name (e.g., dxMakeOrder -> dx_make_order)
        tool_name = self._to_tool_name(rpc_method)

        endpoint = EndpointSpec(
            rpc_method=rpc_method,
            tool_name=tool_name,
        )

        # Extract main description (first paragraph after code block)
        endpoint.description = self._extract_description(section)

        # Extract notes (### sections)
        endpoint.notes = self._extract_notes(section)

        # Parse request parameters
        endpoint.params = self._parse_params(section)

        # Extract sample request/response
        endpoint.sample_request = self._extract_sample(section, "request")
        endpoint.sample_response = self._extract_sample(section, "response")

        # Infer response type from sample response format
        if endpoint.sample_response:
            sample = endpoint.sample_response.strip()
            # Extract first token to handle multi-line responses
            first_token = sample.split()[0] if sample.split() else sample

            if first_token.startswith("["):
                endpoint.response_type = "list"
            elif first_token.startswith("{"):
                endpoint.response_type = "dict"
            elif first_token.lower() in ("true", "false"):
                endpoint.response_type = "bool"
            elif first_token.isdigit() or (first_token.startswith("-") and first_token[1:].isdigit()):
                endpoint.response_type = "int"
            elif re.match(r"^-?\d+\.\d+$", first_token):
                endpoint.response_type = "float"
            elif (first_token.startswith('"') and first_token.endswith('"')) or (first_token.startswith("'") and first_token.endswith("'")):
                endpoint.response_type = "str"
            else:
                # Unknown format - keep safe default
                endpoint.response_type = "dict"

        # Parse error codes
        endpoint.error_codes = self._parse_endpoint_error_codes(section)

        return endpoint

    def _extract_description(self, section: str) -> str:
        """Extract the main description of the endpoint"""
        # Remove unwanted markup to isolate description text

        # Remove blockquote lines (e.g., "> Sample Data", "> Request", etc.)
        section = re.sub(r"^>.*$", "", section, flags=re.MULTILINE)
        # Remove all code blocks
        section = re.sub(r"```.*?```", "", section, flags=re.DOTALL)
        # Remove aside elements (HTML)
        section = re.sub(r"<aside.*?</aside>", "", section, flags=re.DOTALL)
        # Remove all markdown headers (##, ###, etc.)
        section = re.sub(r"^#{1,3}\s+.*$", "", section, flags=re.MULTILINE)

        # Split into paragraphs and find first meaningful text
        for paragraph in section.split("\n\n"):
            para = paragraph.strip()
            if not para:
                continue
            # Skip table-like lines (e.g., "Key | Type | Description")
            if re.match(r"^[A-Za-z]+\s*\|", para):
                continue
            # Skip separator lines
            if re.match(r"^[-=]+$", para):
                continue
            # Clean up whitespace and return first 500 chars
            clean = re.sub(r"\s+", " ", para)
            return clean[:500]

        return ""

    def _extract_notes(self, section: str) -> list[str]:
        """Extract note sections (### Input Selection, ### Fees, etc.)"""
        notes = []

        # Find all ### subsections
        pattern = r"### ([^\n]+)\s*\n(.*?)(?=###|\Z)"
        matches = re.finditer(pattern, section, re.DOTALL)

        for match in matches:
            title = match.group(1).strip()
            content = match.group(2).strip()
            # Clean content
            content = re.sub(r"\n+", " ", content)
            content = content[:300]  # Limit length

            # Only include important notes
            important = ["note", "input", "fee", "asset", "trade", "warning"]
            if any(word in title.lower() for word in important):
                notes.append(f"{title}: {content}")

        return notes

    def _parse_params(self, section: str) -> list[ParamSpec]:
        """Parse parameter table from endpoint section"""
        request_text = self._extract_request_parameters_section(section)
        if not request_text:
            return []

        if self._has_no_parameters_statement(request_text):
            return []

        table_content = self._extract_parameter_table(request_text)
        if not table_content:
            return []

        return self._parse_parameter_rows(table_content)

    def _extract_request_parameters_section(self, section: str) -> str | None:
        """Extract the 'Request Parameters' subsection content"""
        match = re.search(r"### Request Parameters\s*\n(.*?)(?=### |\Z)", section, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _has_no_parameters_statement(self, text: str) -> bool:
        """Check if endpoint explicitly states it has no parameters"""
        return bool(re.search(r"does not take parameters", text, re.IGNORECASE))

    def _extract_parameter_table(self, text: str) -> str | None:
        """Extract markdown table rows from the parameters section"""
        patterns = [
            r"Parameter\s*\|\s*Type\s*\|\s*Description\s*\n[-|]+\|[-|]+\|[-|]+\n(.*?)(?=\n###|\Z)",
            r"Key\s*\|\s*Type\s*\|\s*Description\s*\n[-|]+\|[-|]+\|[-|]+\n(.*?)(?=\n###|\Z)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _parse_parameter_rows(self, table_content: str) -> list[ParamSpec]:
        """Parse each markdown table row into ParamSpec objects"""
        params = []
        for line in table_content.split("\n"):
            line = line.strip()
            if not line or line.startswith("<!--") or line.startswith("-") or re.match(r"^[\s|-]+$", line):
                continue
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) < 2:
                continue
            param = self._create_param_from_parts(parts)
            if param:
                params.append(param)
        return params

    def _create_param_from_parts(self, parts: list[str]) -> ParamSpec | None:
        """Construct a ParamSpec from split table row parts"""
        name = parts[0]
        if name == "Parameter":
            return None
        p_type = parts[1] if len(parts) > 1 else "string"
        description = parts[2] if len(parts) > 2 else ""
        required = "(Optional Parameter)" not in description and "(optional)" not in description.lower()
        default = self._extract_default_value(description)
        clean_desc = self._clean_parameter_description(description)
        return ParamSpec(
            name=name,
            param_type=p_type,
            required=required,
            description=clean_desc,
            default_value=default,
        )

    def _extract_default_value(self, description: str) -> str | None:
        """Extract default value from parameter description"""
        m = re.search(r"Defaults? to\s*`([^`]+)`", description, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m = re.search(r"Default:\s*`?([^\s.,;]+)`?", description, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def _clean_parameter_description(self, description: str) -> str:
        """Remove metadata and markup from description"""
        description = re.sub(r"<[^>]+>", "", description)
        description = re.sub(r"\(Optional Parameter\)", "", description)
        description = re.sub(r"\(optional\)", "", description, flags=re.IGNORECASE)
        description = re.sub(r"Defaults? to\s*`[^`]+`", "", description, flags=re.IGNORECASE)
        description = re.sub(r"Default:\s*`?[^`\n.,;]+`?", "", description, flags=re.IGNORECASE)
        description = description.strip(" :.,;")
        return description.strip()[:200]

    def _extract_sample(self, section: str, section_type: str) -> str:
        """Extract sample request or response"""
        # Allow optional status code (e.g., "200" in "Sample 200 Response") and both shell/cli code fences
        pattern = rf">\s*Sample\s+(?:\d+\s+)?{section_type}\s*\n\s*```(?:shell|cli)\s*\n(.*?)```"
        match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()[:500]

        return ""

    def _parse_error_codes(self) -> dict[int, str]:
        """Parse global error codes section"""
        error_codes = {}

        # Find the Error Codes section - accepts # Error Codes or ## Error Codes
        pattern = r"#+\s*Error Codes\s*\n\s*\n(.*?)(?=\n#+ |\Z)"
        match = re.search(pattern, self.content, re.DOTALL | re.IGNORECASE)

        if not match:
            return error_codes

        section = match.group(1)

        # Parse table rows using split-based approach to handle spaces in messages
        for line in section.split("\n"):
            line = line.strip()
            # Skip empty lines and separator lines
            if not line or re.match(r"^[-|]+$", line):
                continue
            # Skip header line containing "Code" and "Type" and "Error"
            if "Code" in line and "Type" in line and "Error" in line:
                continue

            # Split by pipe and strip whitespace
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                try:
                    code = int(parts[0])
                    # Message is the third column (index 2), may contain spaces
                    message = parts[2]
                    error_codes[code] = message
                except (ValueError, IndexError):
                    continue

        return error_codes

    def _parse_endpoint_error_codes(self, section: str) -> list[int]:
        """Parse error codes specific to an endpoint"""
        codes = []

        # Find Error Codes table within endpoint
        pattern = r"Error Codes\s*\n.*?\n(.*?)(?:\n\n|\n<!--|\Z)"
        match = re.search(pattern, section, re.DOTALL | re.IGNORECASE)

        if not match:
            return codes

        table_content = match.group(1)

        for line in table_content.split("\n"):
            line = line.strip()
            # Skip empty lines and separator lines
            if not line or re.match(r"^[-|]+$", line):
                continue
            # Skip header line containing "Code" and "Type" and "Error"
            if "Code" in line and "Type" in line and "Error" in line:
                continue

            # Split by pipe and strip whitespace
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 1:
                try:
                    code = int(parts[0])
                    codes.append(code)
                except (ValueError, IndexError):
                    continue

        return codes

    def _to_tool_name(self, rpc_method: str) -> str:
        """Convert RPC method name to MCP tool name (preserve original)"""
        return rpc_method


def parse_api_docs(doc_path: str, rpc_prefix: str) -> ApiSpec:
    """Convenience function to parse API documentation"""

    parser = MarkdownParser(doc_path, rpc_prefix)
    parser.load()
    spec = parser.parse()

    # If no error codes found, try to load from global _errors.md in same directory
    if not spec.error_codes:
        doc_dir = Path(doc_path).parent
        errors_path = doc_dir / "_errors.md"
        if errors_path.exists():
            error_parser = MarkdownParser(str(errors_path), rpc_prefix)
            error_parser.load()
            global_errors = error_parser._parse_error_codes()
            spec.error_codes.update(global_errors)

    return spec


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python parser.py <doc_path> <rpc_prefix>")
        sys.exit(1)

    spec = parse_api_docs(sys.argv[1], sys.argv[2])

    print(f"Found {len(spec.endpoints)} endpoints")
    print(f"Found {len(spec.error_codes)} error codes")
    print()

    for name, ep in spec.endpoints.items():
        print(f"{name} -> {ep.tool_name}")
        print(f"  Description: {ep.description[:200]}")
        print(f"  Params: {len(ep.params)}")
        for p in ep.params:
            req = "required" if p.required else "optional"
            print(f"    - {p.name}: {p.param_type} ({req})")
        print()
