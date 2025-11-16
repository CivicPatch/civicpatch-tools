import { useState, useEffect } from 'haunted';
import { apiConfig } from '../api-config.js';

export const useApi = (component) => {
  const [api, setApi] = useState(apiConfig.getApi());
  
  useEffect(() => {
    return apiConfig.subscribe(() => {
      setApi(apiConfig.getApi());
    });
  }, []);

  return {
      ...api
  };
}
