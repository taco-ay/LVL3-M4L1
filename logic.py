import sqlite3
from datetime import datetime
from config import DATABASE
import os
import cv2
import numpy as np
from math import sqrt, ceil

class DatabaseManager:
    def __init__(self, database):
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS prizes (
                    prize_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image TEXT UNIQUE,
                    used INTEGER DEFAULT 0
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS winners (
                    win_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    prize_id INTEGER,
                    win_time TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
                )
            ''')

    def add_user(self, user_id, user_name):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('INSERT OR IGNORE INTO users (user_id, user_name) VALUES (?, ?)', (user_id, user_name))

    def add_prize(self, image_names):
        conn = sqlite3.connect(self.database)
        with conn:
            for img_name in image_names:
                try:
                    conn.execute('INSERT INTO prizes (image) VALUES (?)', (img_name,))
                except sqlite3.IntegrityError:
                    pass

    def add_winner(self, user_id, prize_id):
        win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            
            cur.execute('SELECT COUNT(*) FROM winners WHERE prize_id = ?', (prize_id,))
            current_winners_count = cur.fetchone()[0]

            if current_winners_count >= 3:
                return False 

            cur.execute('SELECT * FROM winners WHERE user_id = ? AND prize_id = ?', (user_id, prize_id))
            if cur.fetchone():
                return False 

            conn.execute('INSERT INTO winners (user_id, prize_id, win_time) VALUES (?, ?, ?)',
                         (user_id, prize_id, win_time))
            
            if current_winners_count + 1 >= 3:
                self.mark_prize_used_permanent(prize_id)
            
            return True
    

    def get_winners_count(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM winners WHERE prize_id = ?', (prize_id,))
            return cur.fetchone()[0]
        
    def has_user_won(self, user_id, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT 1 FROM winners WHERE user_id = ? AND prize_id = ?', (user_id, prize_id))
            return cur.fetchone() is not None
        
    def get_rating(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('''
            SELECT users.user_name, COUNT(*) as total_wins
            FROM winners
            JOIN users ON winners.user_id = users.user_id
            GROUP BY winners.user_id
            ORDER BY total_wins DESC
            LIMIT 10
        ''')
        return cur.fetchall()

    def get_last_win_time(self, user_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('''
            SELECT win_time FROM winners 
            WHERE user_id = ? 
            ORDER BY win_time DESC LIMIT 1
            ''', (user_id,))
        result = cur.fetchone()
        return result[0] if result else None


    def mark_prize_used_session(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('UPDATE prizes SET used = 1 WHERE prize_id = ?', (prize_id,))

    def mark_prize_used_permanent(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('UPDATE prizes SET used = 1 WHERE prize_id = ?', (prize_id,))

    def get_users(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT user_id FROM users')
            return [row[0] for row in cur.fetchall()]

    def get_prize_img(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT image FROM prizes WHERE prize_id = ?', (prize_id,))
            result = cur.fetchone()
            return result[0] if result else None

    def get_random_prize(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT p.prize_id, p.image 
                FROM prizes p
                LEFT JOIN (SELECT prize_id, COUNT(*) as winner_count FROM winners GROUP BY prize_id) w
                ON p.prize_id = w.prize_id
                WHERE p.used = 0 AND COALESCE(w.winner_count, 0) < 3
                ORDER BY RANDOM() LIMIT 1
            ''')
            return cur.fetchone()
    
    def get_winners_img(self, user_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('''
            SELECT image FROM winners
            INNER JOIN prizes ON
            winners.prize_id = prizes.prize_id
            WHERE user_id = ?''', (user_id, ))
            return [row[0] for row in cur.fetchall()] # Sadece resim adlarını döndürür
    


def create_collage(image_paths):
    images = []
    # Resim dosyalarını okuyup listeye ekleme
    for path in image_paths:
        try:
            image = cv2.imread(path)
            # Eğer resim okunamazsa boş bir siyah resim ekleme
            if image is None:
                print(f"Uyarı: {path} bulunamadı veya okunamadı.")
                images.append(np.zeros((300, 300, 3), dtype=np.uint8)) # Örnek olarak 300x300 boyutunda siyah resim
            else:
                images.append(image)
        except Exception as e:
            print(f"Hata oluştu: {path} - {e}")
            images.append(np.zeros((300, 300, 3), dtype=np.uint8))
    
    if not images:
        return None

    num_images = len(images)
    num_cols = int(sqrt(num_images))
    if num_cols == 0: num_cols = 1
    num_rows = ceil(num_images / num_cols)
    
    # Resimleri aynı boyuta getirme (küçük bir optimizasyon)
    resized_images = [cv2.resize(img, (300, 300)) for img in images]

    collage = np.zeros((int(num_rows * 300), int(num_cols * 300), 3), dtype=np.uint8)
    
    # Resimleri kolaja yerleştirme
    for i, image in enumerate(resized_images):
        row = i // num_cols
        col = i % num_cols
        collage[int(row*300):int((row+1)*300), int(col*300):int((col+1)*300), :] = image
    
    return collage


def hide_img(img_name, base_img_dir='img', base_hidden_img_dir='hidden_img'):
    input_path = os.path.join(base_img_dir, img_name)
    output_path = os.path.join(base_hidden_img_dir, img_name)

    os.makedirs(base_hidden_img_dir, exist_ok=True)

    if not os.path.exists(input_path):
        return

    try:
        image = cv2.imread(input_path)
        if image is None:
            return

        h, w = image.shape[:2]
        small_w, small_h = w // 20, h // 20 
        if small_w == 0: small_w = 1 
        if small_h == 0: small_h = 1

        pixelated = cv2.resize(image, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
        pixelated = cv2.resize(pixelated, (w, h), interpolation=cv2.INTER_NEAREST) 
        
        cv2.imwrite(output_path, pixelated)
    except Exception as e:
        pass


if __name__ == '__main__':
    from config import DATABASE
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    os.makedirs('img', exist_ok=True)
    os.makedirs('hidden_img', exist_ok=True)

    prizes_img = [f for f in os.listdir('img') if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if prizes_img:
        manager.add_prize(prizes_img)
        for img_name in prizes_img:
            if not os.path.exists(os.path.join('hidden_img', img_name)):
                hide_img(img_name)
