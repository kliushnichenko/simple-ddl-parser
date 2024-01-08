from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, List, Optional

from simple_ddl_parser.utils import normalize_name


@dataclass
class BaseData:
    """representation of base sql table data

    exclude_if_not_provided - mean, exclude in output, if was not in data from parser
    """

    __d_name__ = "sql"

    # mandatory fields, should have defaults for inheritance
    table_name: str = None
    # final output field set - dialect
    init_data: dict = field(default=None, metadata={"exclude_always": True})
    # final output field set - dialect
    output_mode: str = field(default="sql", metadata={"exclude_always": True})
    # optional fields
    schema: Optional[str] = field(default=None)
    primary_key: Optional[List[str]] = field(default=None)
    columns: Optional[List[dict]] = field(default_factory=list)
    alter: Optional[Dict] = field(default_factory=dict)
    checks: Optional[List] = field(default_factory=list)
    index: Optional[List] = field(default_factory=list)
    partitioned_by: Optional[List] = field(default_factory=list)
    constraints: Optional[Dict] = field(
        default_factory=dict, metadata={"exclude_if_not_provided": True}
    )
    tablespace: Optional[str] = None
    if_not_exists: Optional[bool] = field(
        default=False, metadata={"exclude_if_not_provided": True}
    )
    partition_by: Optional[dict] = field(
        default_factory=dict, metadata={"exclude_if_not_provided": True}
    )
    table_properties: Optional[dict] = field(
        default_factory=dict, metadata={"exclude_if_empty": True}
    )

    replace: Optional[bool] = field(
        default=None, metadata={"exclude_if_not_provided": True}
    )
    comment: Optional[str] = field(
        default=None,
        metadata={
            "exclude_if_not_provided": True,
        },
    )
    like: Optional[dict] = field(
        default_factory=dict,
        metadata={"exclude_if_not_provided": True},
    )
    # parser-only fields -- start
    unique: Optional[list] = field(
        default_factory=list, metadata={"exclude_always": True}
    )
    unique_statement: Optional[list] = field(
        default_factory=list, metadata={"exclude_always": True}
    )
    ref_columns: Optional[List[Dict]] = field(
        default_factory=list, metadata={"exclude_always": True}
    )
    references: Optional[List[Dict]] = field(
        default_factory=list, metadata={"exclude_always": True}
    )

    # parser-only fields -- end
    def post_process(self):
        pass

    def get(self, value: Hashable, default: Any = None) -> Any:
        return self.__dict__.get(value, default)

    def update(self, input_dict: dict) -> None:
        self.__dict__.update(input_dict)

    def if_not_exist_update(self, input_dict: dict) -> None:
        for key, value in input_dict.items():
            if key not in self.__dict__:
                self.__dict__[key] = value

    def __iter__(self):
        for x in self.__dict__:
            yield x

    def __post_init__(self):
        self.set_unique_columns()
        self.populate_keys()
        self.normalize_ref_columns_in_final_output()
        self.post_process()

    def set_unique_columns(self) -> None:
        unique_keys = ["unique_statement", "constraints"]

        for key in unique_keys:
            if getattr(self, key, None):
                # get column names from unique constraints & statements
                self.set_column_unique_param(key)

    def set_column_unique_param(self, key: str) -> None:
        for column in self.columns:
            if key == "constraints":
                unique = getattr(self, key, {}).get("unique", [])
                if unique:
                    check_in = unique["columns"]
                else:
                    check_in = []
            else:
                check_in = getattr(self, key, {})
            if column["name"] in check_in:
                column["unique"] = True

    def normalize_ref_columns_in_final_output(self):
        for col_ref in self.ref_columns:
            name = col_ref["name"]
            for column in self.columns:
                if name == column["name"]:
                    del col_ref["name"]
                    column["references"] = col_ref

    def populate_keys(self) -> None:
        """primary_key - list of column names, example: "primary_key": ["data_sync_id", "sync_start"],"""

        if not self.primary_key:
            self.get_pk_from_columns_and_constraints()
        else:
            self.remove_pk_from_columns()

        if self.unique:
            self.add_unique_columns()

        for column in self.columns:
            if column["name"] in self.primary_key:
                column["nullable"] = False

    def remove_pk_from_columns(self) -> None:
        for column in self.columns:
            del column["primary_key"]

    def get_pk_from_columns_and_constraints(self) -> None:
        pk = []
        for column in self.columns:
            if column["primary_key"]:
                pk.append(column["name"])
            del column["primary_key"]
        if self.constraints.get("primary_keys"):
            for key_constraints in self.constraints["primary_keys"]:
                pk.extend(key_constraints["columns"])

        self.primary_key = pk

    def add_unique_columns(self) -> None:
        for column in self.columns:
            if column["name"] in self.unique:
                column["unique"] = True

    def filter_out_output(self, field: str) -> bool:
        cls_fields = self.__dataclass_fields__.items()
        exclude_always_keys = set()
        exclude_if_not_provided = set()
        exclude_if_empty = set()
        exclude_by_dialect_filter = set()

        for key, value in cls_fields:
            if value.metadata.get("exclude_always") is True:
                exclude_always_keys.add(key)
            else:
                if value.metadata.get("exclude_if_not_provided") is True:
                    exclude_if_not_provided.add(key)
                if value.metadata.get("exclude_if_empty") is True:
                    exclude_if_empty.add(key)
                if isinstance(
                    value.metadata.get("output_modes"), list
                ) and self.output_mode not in value.metadata.get("output_modes"):
                    exclude_by_dialect_filter.add(key)
        if field in exclude_always_keys:
            return False
        if field in exclude_if_not_provided and field not in self.init_data:
            return False
        if field in exclude_if_empty and not self.get(field):
            return False
        if field in exclude_by_dialect_filter:
            return False
        return True

    def to_dict(self):
        output = {}
        for key, value in self.__dict__.items():
            if self.filter_out_output(key) is True:
                output[key] = value
        return output


def prepare_alter_columns(self, statement: Dict) -> None:
    """prepare alters column metadata"""
    alter_columns = []
    for num, column in enumerate(statement["columns"]):
        if statement.get("references"):
            alter_columns.append(
                self.create_alter_column_references(
                    num, column, statement["references"]
                )
            )
        else:
            # mean we need to add
            alter_columns.append(column)
    if not self.alter.get("columns"):
        self.alter["columns"] = alter_columns
    else:
        self.alter["columns"].extend(alter_columns)

    table_columns = self.get_normalized_table_columns_names()
    # add columns from 'alter add'
    for column in self.alter["columns"]:
        if normalize_name(column["name"]) not in table_columns:
            self.columns.append(column)

    def get_normalized_table_columns_names(self) -> List[str]:
        return [normalize_name(column["name"]) for column in self.columns]

    @staticmethod
    def create_alter_column_references(
        index: int, column: Dict, ref_statement: Dict
    ) -> Dict:
        """create alter column metadata"""
        column_reference = ref_statement["columns"][index]
        alter_column = {
            "name": column["name"],
            "constraint_name": column.get("constraint_name"),
        }
        alter_column["references"] = deepcopy(ref_statement)
        alter_column["references"]["column"] = column_reference
        del alter_column["references"]["columns"]
        return alter_column
