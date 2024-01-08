from dataclasses import dataclass

from simple_ddl_parser.output.base_data import BaseData
from simple_ddl_parser.output.dialects import CommonDialectsFieldsMixin, dialect_by_name


class TableData:
    cls_prefix = "Dialect"

    @classmethod
    def get_dialect_class(cls, kwargs: dict):
        output_mode = kwargs.get("output_mode")

        if output_mode and output_mode != "sql":
            main_cls = dialect_by_name.get(output_mode)
            cls = dataclass(
                type(
                    f"{main_cls.__name__}{cls.cls_prefix}",
                    (main_cls, CommonDialectsFieldsMixin),
                    {},
                )
            )
        else:
            cls = BaseData

        return cls

    @classmethod
    def pre_load_mods(cls, main_cls, kwargs):
        if main_cls.__d_name__ == "bigquery":
            if kwargs.get("schema"):
                kwargs["dataset"] = kwargs["schema"]

        cls_fields = {field for field in main_cls.__dataclass_fields__}
        table_main_args = {k: v for k, v in kwargs.items() if k in cls_fields}
        table_properties = {k: v for k, v in kwargs.items() if k not in table_main_args}
        init_data = {}
        init_data.update(table_main_args)
        init_data.update(table_properties)
        kwargs = table_main_args
        kwargs["table_properties"] = table_properties
        kwargs["init_data"] = init_data
        return kwargs

    @classmethod
    def init(cls, **kwargs):
        main_cls = cls.get_dialect_class(kwargs)
        cls.pre_load_mods(main_cls, kwargs)

        kwargs = cls.pre_load_mods(main_cls, kwargs)

        ret = main_cls(**kwargs)
        return ret

    def __new__(cls, *args, **kwargs):
        return cls.__new__(*args, **kwargs)
