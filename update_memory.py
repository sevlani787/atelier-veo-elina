import asyncio
import json
from bot.services.database import Database

async def update_persona():
    db = Database(db_path="elin.db")
    await db.init()
    
    # Получаем текущий профиль:
    persona = await db.get_persona()
    
    print("До:", persona)
    
    # Обновляем или добавляем новые черты
    persona["Творчество"] = "Абстрактная живопись маслом в светлой мастерской как форма медитации"
    persona["Спутники жизни"] = "Дымчато-серая кошка с янтарными глазами по имени Луна, ретро-автомобиль песочного цвета для путешествий, а также гнедая лошадь для утренней верховой езды"
    
    # Сохраняем обновленный профиль:
    await db.save_persona(json.dumps(persona, ensure_ascii=False))
    
    updated_persona = await db.get_persona()
    print("После:", updated_persona)

if __name__ == "__main__":
    asyncio.run(update_persona())
