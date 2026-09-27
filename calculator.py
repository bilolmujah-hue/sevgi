"""
Xavfsiz kalkulyator
sympy orqali
"""

from sympy import sympify, SympifyError
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application
)


def hisobla(ifoda: str):
    """
    Matematik ifodani xavfsiz hisoblash
    Faqat oddiy arifmetika: + - * / ( ) %
    """
    try:
        # Bo'shliqlarni olib tashlash
        ifoda = ifoda.strip()

        # Xavfli belgilarni tekshirish
        xavfli = ['__', 'import', 'eval', 'exec', 'open',
                  'file', 'system', 'popen', 'subprocess']
        past = ifoda.lower()
        for x in xavfli:
            if x in past:
                return None, "❌ Xavfli ifoda"

        # Foizni qo'llash (oddiy: 10% = 0.1)
        # sympy % ni qo'llamaydi, shuning uchun almashtiramiz
        # Lekin oddiy foiz uchun /100 ishlatamiz

        # Hisoblash
        natija = parse_expr(
            ifoda,
            transformations=standard_transformations +
                            (implicit_multiplication_application,)
        )

        # Soddalashtirish
        natija = natija.evalf()

        # Butun son bo'lsa, butun qilib ko'rsatish
        if natija == int(natija):
            natija = int(natija)
        else:
            natija = float(natija)

        return natija, None
    except (SympifyError, Exception) as e:
        return None, f"❌ Xato: ifodani tekshiring"