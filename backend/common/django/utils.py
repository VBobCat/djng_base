import datetime
import decimal
import json
import random
import uuid
import warnings
from pprint import pp
from typing import Any, Callable, Type, TypeVar

from django.db import IntegrityError, models, OperationalError, transaction, DataError
from django.db.models import Func
from django.db.models.options import Options

from ..typing.coerce import Coerce

TModel = TypeVar('TModel', bound=models.Model)

FIELD_PYTHON_TYPES = {
    'AutoField': int,
    'BigAutoField': int,
    'BooleanField': bool,
    'CharField': str,
    'DateField': datetime.date,
    'DateTimeField': datetime.datetime,
    'DecimalField': decimal.Decimal,
    'FloatField': float,
    'IntegerField': int,
    'BigIntegerField': int,
}
BLANK = {'default': '', 'blank': True}
NULLABLE: dict = {'null': True, 'blank': True}
NULLABLE_REL = {'on_delete': models.SET_NULL, **NULLABLE}
PNULLABLE_REL = {'on_delete': models.PROTECT, **NULLABLE}
DECIMAL_DEFAULTS = {'max_digits': 24, 'decimal_places': 2, 'default': decimal.Decimal('0.00')}
DECIMAL_CURRENCY = {'max_digits': 15, 'decimal_places': 2, 'default': decimal.Decimal('0.00')}
DECIMAL_PERCENT = {'max_digits': 15, 'decimal_places': 12, 'default': decimal.Decimal('0.00')}


@transaction.atomic
def dict_to_model_instance(
    model_class: Type[TModel],
    data: dict[str, Any],
    *,
    get_or_create: bool = False,
    cache: dict | None = None,
    preprocessor: Callable[[dict[str, Any]], dict[str, Any]] = None,
) -> TModel | None:
    """
    Constrói (ou atualiza) uma instância Django Model a partir de um dicionário,
    de forma recursiva e transacional, preservando o comportamento original.
    """
    if not data:
        return None
    if preprocessor:
        data = preprocessor(data)

    cache = cache or {}

    # --- Evita loops recursivos em relacionamentos circulares ---
    pk_value = data.get(model_class._meta.pk.name) if model_class._meta.pk else None
    visited_key = (model_class, pk_value)
    if visited_key in cache:
        return cache[visited_key]

    with transaction.atomic(savepoint=False):  # reaproveita transação ativa
        data = data.copy()
        model_options: Options = model_class._meta
        model_pk_field: models.Field = model_options.pk
        model_pk_field_type = FIELD_PYTHON_TYPES.get(model_pk_field.get_internal_type()) if model_pk_field else None

        # --- Verifica cache e reuso de instâncias já buscadas ---
        instance = None
        if model_pk_field and pk_value:
            if (model_class, pk_value) in cache:
                return cache[(model_class, pk_value)]
            try:
                instance = model_class.objects.get(pk=pk_value)
                cache[(model_class, pk_value)] = instance
                if get_or_create:
                    return instance
            except model_class.DoesNotExist:
                instance = model_class(pk=pk_value)

        if instance is None:
            instance = model_class()

        model_fields = model_options.get_fields(include_parents=True, include_hidden=True)

        transposition = [
            (field, data.get(field.name))
            for field in model_fields
            if field and field.name in data and field.name != model_pk_field.name
        ]

        postsave_transposition = []

        for field, new_value in transposition:
            # --- Relacionamentos (FK, O2O, reversos) ---
            if field.is_relation and new_value is not None:
                related_model = model_class if field.related_model == 'self' else field.related_model
                if not isinstance(field, (models.ForeignKey, models.OneToOneField)):
                    postsave_transposition.append((field, new_value))
                    continue

                # --- Criação recursiva de objetos relacionados ---
                if isinstance(new_value, dict):
                    new_value = dict_to_model_instance(
                        related_model, new_value,
                        get_or_create=get_or_create,
                        cache=cache,
                        preprocessor=preprocessor,
                    )
                elif isinstance(new_value, list) and all(isinstance(element, dict) for element in new_value):
                    new_value = [
                        dict_to_model_instance(
                            related_model, element,
                            get_or_create=get_or_create,
                            cache=cache,
                            preprocessor=preprocessor,
                        ) for element in new_value
                    ]
                elif isinstance(new_value, model_pk_field_type):
                    # Reutiliza cache ou busca no banco
                    cached = cache.get((related_model, new_value))
                    if cached:
                        new_value = cached
                    else:
                        new_value = related_model.objects.get(pk=new_value)
                        cache[(related_model, new_value.pk)] = new_value
                elif not isinstance(new_value, related_model):
                    raise AssertionError(
                        f"Invalid value for field {field.name}. "
                        f"Expected {related_model.__name__}, dict, list or {model_pk_field_type.__name__}, "
                        f"got {type(new_value)}.",
                    )

            # --- Tipos especiais ---
            elif isinstance(field, models.JSONField):
                if isinstance(new_value, str):
                    try:
                        new_value = json.loads(new_value, cls=field.decoder)
                    except json.JSONDecodeError:
                        pass
            elif isinstance(field, models.DateTimeField) and isinstance(new_value, str):
                new_value = Coerce.as_datetime(new_value)
            elif isinstance(field, models.DateField) and isinstance(new_value, str):
                new_value = Coerce.as_date(new_value)
            elif isinstance(field, models.UUIDField) and isinstance(new_value, str):
                try:
                    new_value = uuid.UUID(hex=''.join(c for c in new_value if c.casefold() in '0123456789abcdef'))
                except ValueError:
                    new_value = None if field.null else uuid.UUID(
                        hex=''.join(
                            (c if c in '0123456789abcdef' else random.choice('0123456789abcdef')
                             for c in new_value if c.casefold().isalnum()),
                        ),
                    )
            elif isinstance(field, models.DecimalField) and isinstance(new_value, str):
                try:
                    new_value = decimal.Decimal(new_value.replace(',', '.'))
                except Exception as e:
                    warnings.warn(str(e))

            setattr(instance, field.name, new_value)

        # --- Salva e registra no cache ---
        try:
            instance.save()
            cache[(model_class, instance.pk)] = instance
        except (DataError, IntegrityError) as data_integrity_error:
            print(data_integrity_error)
            print(*data_integrity_error.args, sep='\n')
            pp(
                dict(
                    model_class=model_class,
                    data=data,
                    get_or_create=get_or_create,
                    cache=cache,
                ),
            )
            raise

        # --- Trata relacionamentos reversos (OneToMany, ManyToMany) ---
        if postsave_transposition:
            for field, new_value in postsave_transposition:
                related_model = model_class if field.related_model == 'self' else field.related_model

                # OneToOneRel / ManyToOneRel
                if isinstance(field, (models.OneToOneRel, models.ManyToOneRel)) and isinstance(new_value, dict):
                    new_value[field.remote_field.name] = instance.pk
                    dict_to_model_instance(
                        related_model, new_value,
                        get_or_create=get_or_create,
                        cache=cache,
                        preprocessor=preprocessor,
                    )

                # ManyToOneRel (lista)
                elif isinstance(field, models.ManyToOneRel) and isinstance(new_value, list):
                    for element in new_value:
                        element[field.remote_field.name] = instance.pk
                        dict_to_model_instance(
                            related_model, element,
                            get_or_create=get_or_create,
                            cache=cache,
                            preprocessor=preprocessor,
                        )

                # ManyToManyField (direto)
                elif isinstance(field, models.ManyToManyField) and isinstance(new_value, list):
                    ids = []
                    for elem in new_value:
                        if isinstance(elem, dict):
                            # noinspection PyTypeChecker
                            obj = dict_to_model_instance(
                                field.related_model, elem,
                                get_or_create=get_or_create,
                                cache=cache,
                                preprocessor=preprocessor,
                            )
                            ids.append(obj.pk)
                        elif isinstance(elem, (int, str)):
                            ids.append(elem)
                    getattr(instance, field.name).set(ids)

                else:
                    print(field, new_value)

        return instance


class Mode(Func):
    function = 'MODE'
    template = '%(function)s() WITHIN GROUP (ORDER BY %(expressions)s)'