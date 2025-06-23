import csv
from app import db, Question

# The exact filename of your question bank.
CSV_FILENAME = 'NMC Question Bank.csv'

def import_questions():
    """
    A function to read the CSV file and import questions into the database.
    It checks if a question already exists before adding it.
    """
    print(f"Starting import from {CSV_FILENAME}...")
    
    # Open the CSV file for reading
    try:
        # 'with' statement ensures the file is properly closed
        # 'encoding='utf-8-sig'' helps handle special characters
        with open(CSV_FILENAME, mode='r', encoding='utf-8-sig') as csv_file:
            # DictReader reads rows as dictionaries, using the header row for keys
            csv_reader = csv.DictReader(csv_file)
            
            imported_count = 0
            skipped_count = 0

            # Loop through each row in the CSV
            for row in csv_reader:
                # Get the question text from the 'Questions' column
                question_text = row['Questions']
                
                # Check if a question with the same text already exists in the database
                exists = Question.query.filter_by(question_text=question_text).first()
                
                if exists:
                    # If it exists, skip to the next row
                    skipped_count += 1
                    continue
                else:
                    # If it doesn't exist, create a new Question object
                    new_question = Question(
                        question_text=row['Questions'],
                        option_a=row['Option a'],
                        option_b=row['Option b'],
                        option_c=row['Option c'],
                        option_d=row['Option d'],
                        # .lower() makes the answer consistent (e.g., 'A' becomes 'a')
                        correct_answer=row['Correct Answer'].lower(),
                        explanation=row['Explanation'],
                        topic=row['SUBJECT'],
                        difficulty=row['Level of Difficulty'],
                        source=row['Source']
                    )
                    # Add the new question to our database session
                    db.session.add(new_question)
                    imported_count += 1

            # After the loop, commit all the changes to save them to the database
            db.session.commit()
            print(f"Import complete!")
            print(f"Successfully imported {imported_count} new questions.")
            print(f"Skipped {skipped_count} questions that already existed.")

    except FileNotFoundError:
        print(f"ERROR: The file '{CSV_FILENAME}' was not found.")
        print("Please make sure the CSV file is in the same folder as this script.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


# This part allows the script to be run directly from the terminal
if __name__ == '__main__':
    # We need to run this within the 'app context' so it can access the database
    from app import app
    with app.app_context():
        import_questions()