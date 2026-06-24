import pandas as pd
import numpy as np
import random

def generate_student_data(num_students=200):
    data = []
    
    # Messy Real-World Data Generation
    # Instead of perfectly separated groups, we generate a continuum.
    # We use a broad normal distribution so students are everywhere.
    
    for _ in range(num_students):
        # Base Intelligence/Effort (Hidden Latent Variables)
        # Some are smart (high logic), some hardworking (high completion)
        # But we mix them up randomly so there are no clear "types" initially.
        
        logic_latent = np.random.normal(5, 2.5)       # 0-10 scale (original latent logic)
        effort_latent = np.random.normal(50, 25)      # 0-100 scale (original latent effort)
        social_latent = np.random.normal(5, 2.5)      # 0-10 scale (original latent social)
        
        # Derived Metrics with Noise
        # Make it messy: Randomize heavily
        # Exam score: Normal distribution centered at 60, spread 20
        exam_score = int(np.clip(np.random.normal(60, 20), 30, 98))
        
        # Engagement metrics: Independent randoms to break correlation
        participation = int(np.clip(np.random.normal(5, 3), 1, 10))
        assignment = int(np.clip(np.random.normal(70, 25), 20, 100))
        depth = int(np.clip(np.random.normal(5, 2.5), 1, 10))
        curiosity = int(np.clip(np.random.normal(5, 2.5), 1, 10))
        self_learning = int(np.clip(np.random.normal(5, 2.5), 1, 10))
        question_freq = int(np.clip(np.random.normal(5, 2.5), 1, 10))
        logical_understanding = int(np.clip(np.random.normal(5, 2.5), 1, 10)) # Independent random for logical understanding
        
        data.append({
            'participation_frequency': participation,
            'assignment_completion': assignment,
            'depth_of_doubts': depth,
            'curiosity_level': curiosity,
            'self_learning': self_learning,
            'question_frequency': question_freq,
            'exam_score': exam_score,
            'logical_understanding': logical_understanding
        })

    # Convert to DataFrame
    df = pd.DataFrame(data)
    
    # Clip values to realistic ranges
    df['participation_frequency'] = df['participation_frequency'].clip(0, 10)
    df['assignment_completion'] = df['assignment_completion'].clip(0, 100)
    df['depth_of_doubts'] = df['depth_of_doubts'].clip(0, 10)
    df['curiosity_level'] = df['curiosity_level'].clip(0, 10)
    df['self_learning'] = df['self_learning'].clip(0, 10)
    df['question_frequency'] = df['question_frequency'].clip(0, 10)
    df['exam_score'] = df['exam_score'].clip(0, 100)
    df['logical_understanding'] = df['logical_understanding'].clip(0, 10)

    # Add Student IDs
    df.insert(0, 'student_id', [f'STU{i:03d}' for i in range(1, num_students + 1)])

    # Shuffle the dataset so groups aren't contiguous
    df = df.sample(frac=1).reset_index(drop=True)
    
    return df

if __name__ == "__main__":
    print("Generating Synthetic Student Data...")
    df = generate_student_data(60)
    
    # Save to CSV
    output_file = 'student_data.csv'
    df.to_csv(output_file, index=False)
    
    print(f"Data generated successfully and saved to {output_file}")
    print("\nSample Data:")
    print(df.head())
    print("\nDataset Statistics:")
    print(df.describe())
